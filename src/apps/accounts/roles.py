"""Wine House — rol tanımları ve yetki haritası.

Her rol bir Django ``Group`` olarak veritabanına yansıtılır. Yetkiler
``uygulama.izin_kodu`` biçiminde veya ``uygulama.*`` joker deseniyle verilir.

Tasarım ilkeleri:
  * **En az yetki**: her rol yalnızca görevini yapmak için gereken izinlere sahiptir.
  * **Ayrıcalık ayrımı**: mali işlemler (iade, iptal, indirim) ayrı izinlerdir.
  * **İkinci onay**: kritik işlemler ``requires_second_approval`` listesindedir.
  * **Salt okunur denetçi**: hiçbir yazma izni almaz.

Yetki adları henüz var olmayan uygulamalara ait olabilir; ``sync_roles``
bilinmeyen izinleri atlar ve raporlar. Böylece modüller aşamalı geliştirilirken
rol tanımları bozulmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Yetki kümeleri (yeniden kullanılabilir bloklar)
# ---------------------------------------------------------------------------

READ_ONLY_ALL = [
    "core.view_auditlog",
    "catalog.*view*",
    "cellar.*view*",
    "inventory.*view*",
    "operations.*view*",
    "crm.*view*",
    "hr.*view*",
    "reporting.*view*",
]

SERVICE_FLOOR = [
    "operations.view_diningtable",
    "operations.change_diningtable",
    "operations.view_order",
    "operations.add_order",
    "operations.change_order",
    "operations.view_orderline",
    "operations.add_orderline",
    "operations.change_orderline",
    "operations.delete_orderline",
    "operations.can_open_table",
    "operations.can_transfer_table",
    "operations.can_split_bill",
    "operations.can_merge_orders",
    "operations.view_reservation",
    "catalog.view_menuitem",
    "catalog.view_menucategory",
    "cellar.view_wine",
    "crm.view_customer",
]

KITCHEN = [
    "operations.view_prepticket",
    "operations.change_prepticket",
    "operations.view_prepticketline",
    "operations.change_prepticketline",
    "operations.can_bump_ticket",
    "operations.can_view_kitchen_display",
    "operations.view_order",
    "operations.view_orderline",
    "catalog.view_menuitem",
    "catalog.view_recipe",
    "catalog.view_recipeline",
    "catalog.view_allergen",
]

CELLAR_FULL = [
    "cellar.*",
]

INVENTORY_FULL = [
    "inventory.*",
]

REPORTING_FULL = [
    "reporting.*",
]


@dataclass(frozen=True)
class RoleSpec:
    """Tek bir rolün tanımı."""

    code: str
    name_tr: str
    name_en: str
    #: Yönetim kademesi: 0 = en yüksek. Yalnızca raporlama/sıralama içindir.
    level: int
    description_tr: str
    permissions: list[str] = field(default_factory=list)
    #: Bu rolün onaylayabileceği kritik işlemler
    can_approve: list[str] = field(default_factory=list)
    #: Django ``is_staff`` bayrağı (Django yönetim paneline erişim)
    django_staff: bool = False


# ---------------------------------------------------------------------------
# Kritik işlemler — ikinci onay gerektirebilir
# ---------------------------------------------------------------------------
CRITICAL_ACTIONS: dict[str, str] = {
    "void_order": "Sipariş iptali",
    "refund_payment": "Ödeme iadesi",
    "discount_over_limit": "Yetki sınırını aşan indirim",
    "comp_item": "İkram (bedelsiz ürün)",
    "stock_adjust": "Stok düzeltmesi",
    "waste_high_value": "Yüksek değerli fire kaydı",
    "price_override": "Fiyat değiştirme",
    "close_day": "Gün sonu kapanışı",
    "restore_backup": "Yedekten geri yükleme",
    "erase_customer_data": "Müşteri verisi silme (KVKK)",
    "apply_ai_change": "Yapay zekâ önerisini uygulama",
    "devstudio_merge": "Geliştirici stüdyosu birleştirme",
}


# ---------------------------------------------------------------------------
# Rol kataloğu
# ---------------------------------------------------------------------------
ROLES: tuple[RoleSpec, ...] = (
    RoleSpec(
        code="owner",
        name_tr="İşletme Sahibi",
        name_en="Business Owner",
        level=0,
        description_tr="Tüm modüllere ve mali raporlara tam erişim.",
        permissions=["*"],
        can_approve=list(CRITICAL_ACTIONS),
        django_staff=True,
    ),
    RoleSpec(
        code="general_manager",
        name_tr="Genel Müdür",
        name_en="General Manager",
        level=1,
        description_tr="İşletme genelinde yönetim, mali raporlar ve onaylar.",
        permissions=["*"],
        can_approve=list(CRITICAL_ACTIONS),
        django_staff=True,
    ),
    RoleSpec(
        code="restaurant_manager",
        name_tr="Restoran Müdürü",
        name_en="Restaurant Manager",
        level=2,
        description_tr="Günlük salon operasyonu, personel ve gün sonu yönetimi.",
        permissions=[
            "operations.*",
            "catalog.*",
            "crm.*",
            "hr.view_*",
            "hr.change_shift",
            "hr.add_shift",
            "inventory.view_*",
            "cellar.view_*",
            "reporting.*",
            "core.view_auditlog",
            "backups.add_backuprecord",
            "backups.view_backuprecord",
        ],
        can_approve=[
            "void_order",
            "refund_payment",
            "discount_over_limit",
            "comp_item",
            "price_override",
            "close_day",
            "waste_high_value",
        ],
        django_staff=True,
    ),
    RoleSpec(
        code="head_sommelier",
        name_tr="Baş Sommelier",
        name_en="Head Sommelier",
        level=3,
        description_tr="Şarap kavı yönetimi, şarap listesi, eşleştirme ve tadım etkinlikleri.",
        permissions=[
            *CELLAR_FULL,
            "catalog.view_menuitem",
            "catalog.add_menuitem",
            "catalog.change_menuitem",
            "catalog.view_menucategory",
            "operations.view_order",
            "operations.view_orderline",
            "operations.view_prepticket",
            "operations.change_prepticket",
            "operations.can_view_wine_display",
            "operations.can_bump_ticket",
            "inventory.view_*",
            "inventory.add_wastageentry",
            "crm.view_customer",
            "reporting.view_*",
            "reporting.can_export_report",
        ],
        can_approve=["waste_high_value"],
    ),
    RoleSpec(
        code="sommelier",
        name_tr="Sommelier",
        name_en="Sommelier",
        level=4,
        description_tr="Şarap servisi, öneri, kadeh/şişe satışı ve tadım notları.",
        permissions=[
            "cellar.view_*",
            "cellar.add_tastingnote",
            "cellar.change_tastingnote",
            "cellar.add_bottleopening",
            "cellar.change_bottleopening",
            "cellar.add_pouringrecord",
            "cellar.add_winepairing",
            "cellar.change_winepairing",
            "cellar.can_open_bottle",
            "cellar.can_pour_glass",
            "cellar.can_record_wine_fault",
            "operations.view_order",
            "operations.add_orderline",
            "operations.change_orderline",
            "operations.view_prepticket",
            "operations.change_prepticket",
            "operations.can_view_wine_display",
            "catalog.view_menuitem",
            "crm.view_customer",
        ],
    ),
    RoleSpec(
        code="cellar_master",
        name_tr="Kav ve Şarap Deposu Sorumlusu",
        name_en="Cellar Master",
        level=4,
        description_tr="Kav yerleşimi, sıcaklık/nem kayıtları, şişe girişi ve sayım.",
        permissions=[
            *CELLAR_FULL,
            "inventory.view_*",
            "inventory.add_stockmovement",
            "inventory.add_stockcount",
            "inventory.change_stockcount",
            "inventory.add_wastageentry",
            "inventory.add_goodsreceipt",
            "inventory.change_goodsreceipt",
        ],
    ),
    RoleSpec(
        code="executive_chef",
        name_tr="Executive Chef",
        name_en="Executive Chef",
        level=3,
        description_tr="Mutfak yönetimi, reçete ve porsiyon maliyeti, menü mühendisliği.",
        permissions=[
            "catalog.*",
            *KITCHEN,
            "inventory.view_*",
            "inventory.add_wastageentry",
            "inventory.change_wastageentry",
            "inventory.add_purchaserequest",
            "reporting.view_*",
            "reporting.can_export_report",
            "hr.view_employee",
            "hr.view_shift",
        ],
        can_approve=["waste_high_value"],
    ),
    RoleSpec(
        code="kitchen_staff",
        name_tr="Mutfak Personeli",
        name_en="Kitchen Staff",
        level=6,
        description_tr="Mutfak ekranı (KDS) üzerinden sipariş hazırlama.",
        permissions=[*KITCHEN, "inventory.add_wastageentry"],
    ),
    RoleSpec(
        code="waiter",
        name_tr="Garson",
        name_en="Waiter",
        level=6,
        description_tr="Masa açma, sipariş girme, hesap hazırlama.",
        permissions=[*SERVICE_FLOOR],
    ),
    RoleSpec(
        code="busser",
        name_tr="Komi",
        name_en="Busser",
        level=7,
        description_tr="Masa hazırlığı ve durum güncelleme.",
        permissions=[
            "operations.view_diningtable",
            "operations.change_diningtable",
            "operations.view_order",
            "catalog.view_menuitem",
        ],
    ),
    RoleSpec(
        code="bartender",
        name_tr="Barmen",
        name_en="Bartender",
        level=6,
        description_tr="Bar ekranı, içecek hazırlama, kadeh servisi.",
        permissions=[
            "operations.view_prepticket",
            "operations.change_prepticket",
            "operations.view_prepticketline",
            "operations.change_prepticketline",
            "operations.can_view_bar_display",
            "operations.can_view_wine_display",
            "operations.view_order",
            "operations.view_orderline",
            "operations.add_orderline",
            "operations.can_bump_ticket",
            "catalog.view_menuitem",
            "cellar.view_wine",
            "cellar.view_bottleopening",
            "cellar.add_pouringrecord",
            "cellar.can_pour_glass",
            "inventory.add_wastageentry",
        ],
    ),
    RoleSpec(
        code="cashier",
        name_tr="Kasiyer",
        name_en="Cashier",
        level=5,
        description_tr="Ödeme alma, hesap bölme, fiş yazdırma.",
        permissions=[
            "operations.view_order",
            "operations.change_order",
            "operations.view_orderline",
            "operations.view_payment",
            "operations.add_payment",
            "operations.can_take_payment",
            "operations.can_split_bill",
            "operations.can_print_receipt",
            "operations.view_diningtable",
            "catalog.view_menuitem",
            "crm.view_customer",
            "crm.change_loyaltyaccount",
        ],
    ),
    RoleSpec(
        code="host",
        name_tr="Rezervasyon Görevlisi",
        name_en="Host / Reservations",
        level=6,
        description_tr="Rezervasyon, bekleme listesi ve müşteri karşılama.",
        permissions=[
            "operations.view_reservation",
            "operations.add_reservation",
            "operations.change_reservation",
            "operations.view_waitlistentry",
            "operations.add_waitlistentry",
            "operations.change_waitlistentry",
            "operations.view_diningtable",
            "operations.change_diningtable",
            "operations.can_seat_guest",
            "crm.view_customer",
            "crm.add_customer",
            "crm.change_customer",
            "catalog.view_menuitem",
        ],
    ),
    RoleSpec(
        code="purchasing",
        name_tr="Satın Alma Sorumlusu",
        name_en="Purchasing Officer",
        level=4,
        description_tr="Tedarikçi yönetimi, teklif karşılaştırma, satın alma siparişi.",
        permissions=[
            *INVENTORY_FULL,
            "cellar.view_*",
            "cellar.add_wine",
            "cellar.change_wine",
            "catalog.view_*",
            "reporting.view_*",
            "reporting.can_export_report",
        ],
    ),
    RoleSpec(
        code="warehouse",
        name_tr="Depo Görevlisi",
        name_en="Warehouse Clerk",
        level=6,
        description_tr="Mal kabul, transfer, sayım ve fire kaydı.",
        permissions=[
            "inventory.view_*",
            "inventory.add_goodsreceipt",
            "inventory.change_goodsreceipt",
            "inventory.add_stockmovement",
            "inventory.add_stocktransfer",
            "inventory.change_stocktransfer",
            "inventory.add_stockcount",
            "inventory.change_stockcount",
            "inventory.add_wastageentry",
            "cellar.view_*",
            "cellar.change_winestoragelocation",
        ],
    ),
    RoleSpec(
        code="accounting",
        name_tr="Muhasebe",
        name_en="Accounting",
        level=3,
        description_tr="Mali raporlar, ödeme mutabakatı, maliyet ve kârlılık analizi.",
        permissions=[
            "operations.view_*",
            "inventory.view_*",
            "cellar.view_*",
            "catalog.view_*",
            "crm.view_customer",
            "reporting.*",
            "core.view_auditlog",
        ],
        can_approve=["refund_payment", "close_day"],
    ),
    RoleSpec(
        code="hr",
        name_tr="İnsan Kaynakları",
        name_en="Human Resources",
        level=3,
        description_tr="Personel kartları, vardiya, izin, eğitim kayıtları.",
        permissions=[
            "hr.*",
            "accounts.view_user",
            "accounts.add_user",
            "accounts.change_user",
            "training.*",
            "reporting.view_*",
        ],
    ),
    RoleSpec(
        code="sysadmin",
        name_tr="Sistem Yöneticisi",
        name_en="System Administrator",
        level=1,
        description_tr=(
            "Kullanıcı/rol yönetimi, yedekleme, yapay zekâ ayarları ve "
            "AI Development Studio erişimi."
        ),
        permissions=["*"],
        can_approve=list(CRITICAL_ACTIONS),
        django_staff=True,
    ),
    RoleSpec(
        code="auditor",
        name_tr="Denetçi (Salt Okunur)",
        name_en="Auditor (Read-only)",
        level=2,
        description_tr="Hiçbir yazma yetkisi olmadan tüm kayıtları görüntüleme.",
        permissions=[*READ_ONLY_ALL, "backups.view_backuprecord", "aiservices.view_*"],
    ),
)

ROLES_BY_CODE: dict[str, RoleSpec] = {role.code: role for role in ROLES}

#: Yapay zekâ geliştirici stüdyosuna erişebilecek roller
DEVSTUDIO_ROLES: frozenset[str] = frozenset({"sysadmin", "owner"})

#: Salt okunur roller — arayüzde yazma düğmeleri gizlenir
READ_ONLY_ROLES: frozenset[str] = frozenset({"auditor"})


def role_choices() -> list[tuple[str, str]]:
    """Form/model seçenekleri için ``(kod, ad)`` listesi."""
    return [(role.code, role.name_tr) for role in ROLES]


def can_role_approve(role_code: str, action: str) -> bool:
    """Verilen rolün belirtilen kritik işlemi onaylayıp onaylayamayacağını bildirir."""
    spec = ROLES_BY_CODE.get(role_code)
    if spec is None:
        return False
    return action in spec.can_approve
