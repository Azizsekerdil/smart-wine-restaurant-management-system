# GitHub Actions CI

`github-actions-ci.yml` dosyası projenin sürekli entegrasyon iş akışıdır.

## Neden burada?

GitHub, `.github/workflows/` altına dosya yazılmasına yalnızca **`workflow`
kapsamına sahip** bir belirteçle izin verir. İlk gönderim sırasında kullanılan
belirteçte bu kapsam bulunmadığından iş akışı reddedildi ve kodun geri kalanının
güvenceye alınabilmesi için dosya buraya taşındı.

## Etkinleştirme

Tek seferlik iki komut:

```bash
gh auth refresh -h github.com -s workflow
```

Tarayıcıda izni onayladıktan sonra:

```bash
mkdir -p .github/workflows
git mv docs/ci/github-actions-ci.yml .github/workflows/ci.yml
git commit -m "CI iş akışını etkinleştir"
git push
```

## İş akışı ne yapıyor?

| İş | İçerik |
|---|---|
| `test` | Python 3.11 / 3.12 / 3.13 matrisi · `manage.py check` · bekleyen migration denetimi · pytest + kapsam |
| `quality` | ruff · black · mypy |
| `security` | detect-secrets · pip-audit · bandit · lisans dökümü · **çalışma zamanı bağımlılıklarında güçlü kopyaleft denetimi** |

İş akışı hiçbir gizli değere (secret) ihtiyaç duymaz; testler `winehouse.settings.test`
profiliyle, bellek içi veritabanı ve yalnızca Mock yapay zekâ sağlayıcısıyla çalışır.

## Dal koruma önerileri

Depo ayarlarından `main` dalı için önerilen kurallar:

- Doğrudan push kapalı; değişiklikler pull request ile gelsin
- `test`, `quality` ve `security` işleri zorunlu kontrol olsun
- En az 1 inceleme onayı istensin
- Force push ve dal silme kapalı olsun
