"""AI Development Studio politika motoru.

TEMEL İLKE: Yapay zekâ **hiçbir zaman** doğrudan komut çalıştırmaz. Model
yalnızca *yapılandırılmış eylem önerisi* üretir; bu motor her öneriyi
denetler ve yalnızca izin verilenler kullanıcı onayına sunulur.

Uygulanan koruma katmanları:

  1. **İzin listesi (allowlist)** — yalnızca bilinen güvenli komutlar.
  2. **Yasak desenler (denylist)** — yıkıcı komutlar kesin olarak reddedilir.
  3. **Çalışma alanı sınırı** — yazma yalnızca yapılandırılmış klasörde.
  4. **Kabuk metakarakteri yasağı** — zincirleme/enjeksiyon engellenir.
  5. **Gizli dosya koruması** — ``.env``, anahtarlar ve kimlik dosyaları
     okunamaz ve yazılamaz.
  6. **Git koruması** — ``force push``, ``reset --hard``, geçmiş silme yasak.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.core.security import WorkspaceViolationError, resolve_within_workspace


class Decision(str, Enum):
    """Politika kararı."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass
class PolicyResult:
    """Bir eylemin politika değerlendirmesi."""

    decision: Decision
    reason: str
    matched_rule: str = ""
    normalized_command: list[str] = field(default_factory=list)

    @property
    def is_allowed(self) -> bool:
        return self.decision is not Decision.DENY

    @property
    def badge_class(self) -> str:
        return {
            Decision.ALLOW: "bg-success",
            Decision.REQUIRE_APPROVAL: "bg-warning text-dark",
            Decision.DENY: "bg-danger",
        }[self.decision]


# ---------------------------------------------------------------------------
# Komut politikaları
# ---------------------------------------------------------------------------

#: Onaysız çalıştırılabilecek salt okunur komutlar (yalnızca çalışma alanında)
READ_ONLY_COMMANDS: dict[str, tuple[str, ...]] = {
    "git": ("status", "diff", "log", "show", "branch", "rev-parse", "remote"),
    "python": ("-m",),
    "ruff": ("check", "format"),
    "black": ("--check", "--diff"),
    "mypy": (),
    "pytest": (),
}

#: Onay gerektiren, ancak izin verilebilecek komutlar
APPROVAL_COMMANDS: dict[str, tuple[str, ...]] = {
    "git": ("add", "commit", "checkout", "switch", "stash", "restore"),
    "pip": ("install", "uninstall"),
}

#: Hiçbir koşulda çalıştırılmayacak komutlar
FORBIDDEN_EXECUTABLES: frozenset[str] = frozenset(
    {
        "format",
        "diskpart",
        "fdisk",
        "mkfs",
        "shutdown",
        "reboot",
        "reg",
        "regedit",
        "netsh",
        "sc",
        "schtasks",
        "bcdedit",
        "cipher",
        "vssadmin",
        "wmic",
        "takeown",
        "icacls",
        "cacls",
        "attrib",
        "net",
        "curl",
        "wget",
        "certutil",
        "bitsadmin",
        "powershell",
        "pwsh",
        "cmd",
        "bash",
        "sh",
        "wsl",
        "ssh",
        "scp",
        "rundll32",
        "mshta",
        "wscript",
        "cscript",
    }
)

#: Yıkıcı veya gizli veri sızdıran desenler
FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("git_force_push", re.compile(r"\bgit\b.*\bpush\b.*(--force|-f)\b")),
    ("git_hard_reset", re.compile(r"\bgit\b.*\breset\b.*--hard")),
    ("git_history_rewrite", re.compile(r"\bgit\b.*\b(filter-branch|filter-repo|rebase)\b")),
    ("git_clean", re.compile(r"\bgit\b.*\bclean\b.*-[a-z]*[fdx]")),
    ("recursive_delete", re.compile(r"\b(rm|del|erase|Remove-Item)\b.*(-r|-rf|/s|-Recurse)")),
    ("wildcard_delete", re.compile(r"\b(rm|del|erase)\b.*[*?]")),
    ("credential_read", re.compile(r"(?i)(credential|vault|keychain|keyring|password|secret)")),
    (
        "env_exfiltration",
        re.compile(r"(?i)(printenv|Get-ChildItem\s+env:|\benv\b\s*$|\bset\b\s*$)"),
    ),
    (
        "network_exfiltration",
        re.compile(r"(?i)(curl|wget|Invoke-WebRequest|Invoke-RestMethod|nc\b)"),
    ),
    ("privilege_escalation", re.compile(r"(?i)(runas|sudo|Start-Process.*-Verb\s+RunAs)")),
    ("code_eval", re.compile(r"(?i)(eval|exec)\s*\(")),
)

#: Kabuk zincirleme / yönlendirme karakterleri — komut tek bir çağrı olmalıdır
SHELL_METACHARACTERS: tuple[str, ...] = ("|", "&", ";", ">", "<", "`", "$(", "&&", "||", "\n")

#: Okunması ve yazılması yasak dosya desenleri
PROTECTED_FILE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "id_rsa*",
    "credentials*",
    "secrets*",
    "*.sqlite3",
    "*.sqlite3-wal",
    "*.sqlite3-shm",
)

#: Değiştirilmesi ek onay gerektiren hassas kaynak dosyalar
SENSITIVE_SOURCE_PATTERNS: tuple[str, ...] = (
    "src/winehouse/settings/*",
    "src/apps/core/security.py",
    "src/apps/devstudio/policy.py",
    "src/apps/accounts/roles.py",
    "src/apps/accounts/permissions.py",
    ".github/workflows/*",
    ".gitignore",
    ".pre-commit-config.yaml",
)


def workspace_root() -> Path:
    """Yapılandırılmış çalışma alanı kökü."""
    return Path(settings.DEVSTUDIO.get("WORKSPACE", settings.BASE_DIR)).resolve()


def evaluate_command(raw_command: str) -> PolicyResult:
    """Komut önerisini değerlendirir.

    Args:
        raw_command: Modelin önerdiği komut satırı.

    Returns:
        ``PolicyResult`` — ``DENY`` ise komut hiçbir koşulda çalıştırılmaz.
    """
    command = (raw_command or "").strip()
    if not command:
        return PolicyResult(Decision.DENY, "Boş komut.", matched_rule="empty")

    # 1) Kabuk metakarakteri denetimi — zincirleme ve enjeksiyon engellenir
    for character in SHELL_METACHARACTERS:
        if character in command:
            return PolicyResult(
                Decision.DENY,
                f"Komutta kabuk metakarakteri var ({character!r}). Komutlar tek bir "
                "çağrı olmalı; zincirleme ve yönlendirme yasaktır.",
                matched_rule="shell_metacharacter",
            )

    # 2) Yasak desen denetimi
    for rule_name, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(command):
            return PolicyResult(
                Decision.DENY,
                f"Komut yasak desenle eşleşti: {rule_name}.",
                matched_rule=rule_name,
            )

    # 3) Ayrıştırma
    try:
        parts = shlex.split(command, posix=False)
    except ValueError as exc:
        return PolicyResult(
            Decision.DENY, f"Komut ayrıştırılamadı: {exc}", matched_rule="parse_error"
        )
    if not parts:
        return PolicyResult(Decision.DENY, "Boş komut.", matched_rule="empty")

    executable = Path(parts[0].strip('"')).name.lower()
    executable = executable.removesuffix(".exe")
    subcommand = parts[1].lower() if len(parts) > 1 else ""

    # 4) Yasak çalıştırılabilir denetimi
    if executable in FORBIDDEN_EXECUTABLES:
        return PolicyResult(
            Decision.DENY,
            f"'{executable}' komutunun çalıştırılması yasaktır.",
            matched_rule="forbidden_executable",
            normalized_command=parts,
        )

    # 5) İzin listesi denetimi
    if executable in READ_ONLY_COMMANDS:
        allowed = READ_ONLY_COMMANDS[executable]
        if not allowed or subcommand in allowed or not subcommand:
            return PolicyResult(
                Decision.ALLOW,
                f"Salt okunur komut: {executable} {subcommand}".strip(),
                matched_rule="read_only_allowlist",
                normalized_command=parts,
            )

    if executable in APPROVAL_COMMANDS and subcommand in APPROVAL_COMMANDS[executable]:
        return PolicyResult(
            Decision.REQUIRE_APPROVAL,
            f"Bu komut kullanıcı onayı gerektirir: {executable} {subcommand}",
            matched_rule="approval_allowlist",
            normalized_command=parts,
        )

    return PolicyResult(
        Decision.DENY,
        f"'{command}' izin listesinde değil. AI Development Studio yalnızca "
        "açıkça izin verilen komutları çalıştırır.",
        matched_rule="not_in_allowlist",
        normalized_command=parts,
    )


def evaluate_file_write(target_path: str) -> PolicyResult:
    """Dosya yazma önerisini değerlendirir."""
    root = workspace_root()

    try:
        resolved = resolve_within_workspace(target_path, root)
    except WorkspaceViolationError as exc:
        return PolicyResult(
            Decision.DENY,
            f"Çalışma alanı ihlali. {exc}",
            matched_rule="workspace_violation",
        )

    relative = resolved.relative_to(root).as_posix()

    # Korumalı dosyalar — hiçbir koşulda yazılamaz
    for pattern in PROTECTED_FILE_PATTERNS:
        if _matches(relative, pattern):
            return PolicyResult(
                Decision.DENY,
                f"Korumalı dosyaya yazma engellendi: {relative}",
                matched_rule="protected_file",
            )

    # Git iç dizini
    if relative.startswith(".git/"):
        return PolicyResult(
            Decision.DENY,
            "Git iç dizinine (.git) yazma yasaktır.",
            matched_rule="git_internals",
        )

    # Sanal ortam ve bağımlılıklar
    if relative.startswith((".venv/", "venv/", "site-packages/", "node_modules/")):
        return PolicyResult(
            Decision.DENY,
            "Bağımlılık/sanal ortam dizinine yazma yasaktır.",
            matched_rule="dependency_dir",
        )

    # Hassas kaynak dosyalar — izin var ama ek onay gerekir
    for pattern in SENSITIVE_SOURCE_PATTERNS:
        if _matches(relative, pattern):
            return PolicyResult(
                Decision.REQUIRE_APPROVAL,
                f"Güvenlik açısından hassas dosya: {relative}. Değişiklik ek onay gerektirir.",
                matched_rule="sensitive_source",
            )

    return PolicyResult(
        Decision.REQUIRE_APPROVAL,
        f"Dosya değişikliği kullanıcı onayı gerektirir: {relative}",
        matched_rule="workspace_write",
    )


def evaluate_file_read(target_path: str) -> PolicyResult:
    """Dosya okuma önerisini değerlendirir."""
    root = workspace_root()

    try:
        resolved = resolve_within_workspace(target_path, root)
    except WorkspaceViolationError as exc:
        return PolicyResult(
            Decision.DENY, f"Çalışma alanı ihlali. {exc}", matched_rule="workspace_violation"
        )

    relative = resolved.relative_to(root).as_posix()

    for pattern in PROTECTED_FILE_PATTERNS:
        if _matches(relative, pattern):
            return PolicyResult(
                Decision.DENY,
                f"Gizli bilgi içerebilecek dosya okunamaz: {relative}",
                matched_rule="protected_file",
            )

    return PolicyResult(
        Decision.ALLOW, f"Okuma izni verildi: {relative}", matched_rule="workspace_read"
    )


def _matches(relative_path: str, pattern: str) -> bool:
    """Yol deseni eşleştirmesi (dosya adı ve tam yol üzerinde)."""
    from fnmatch import fnmatch

    name = relative_path.rsplit("/", 1)[-1]
    return fnmatch(relative_path, pattern) or fnmatch(name, pattern)


def studio_enabled() -> bool:
    """AI Development Studio'nun etkin olup olmadığını bildirir."""
    return bool(settings.DEVSTUDIO.get("ENABLED", False))


def commands_allowed() -> bool:
    """Komut çalıştırmanın açık olup olmadığını bildirir."""
    return bool(settings.DEVSTUDIO.get("ALLOW_COMMANDS", False))


def policy_summary() -> dict[str, Any]:
    """Arayüzde gösterilecek politika özeti."""
    return {
        "enabled": studio_enabled(),
        "commands_allowed": commands_allowed(),
        "workspace": str(workspace_root()),
        "read_only_commands": sorted(READ_ONLY_COMMANDS),
        "approval_commands": sorted(APPROVAL_COMMANDS),
        "forbidden_executables": sorted(FORBIDDEN_EXECUTABLES),
        "forbidden_pattern_count": len(FORBIDDEN_PATTERNS),
        "protected_files": list(PROTECTED_FILE_PATTERNS),
        "sensitive_sources": list(SENSITIVE_SOURCE_PATTERNS),
    }
