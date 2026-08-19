# ROPA Hazırlık Çıktısı (VERBİS/GDPR m.30 ön çalışması)

> Bu belge otomatik taramayla üretilmiş bir **hazırlıktır**; resmî kayıt
> veya tamamlanmış işleme envanteri değildir. Amaç ve hukuki dayanak
> alanları DPO/hukuk incelemesi gerektirir (`REVIEW_REQUIRED`).

Tarama kapsamı: 46 model · 431 alan · 55 kişisel veri adayı

## Saklama süresi tanımları (settings.DATA_RETENTION_DAYS)

- `ai_call_log`: 180 gün
- `audit_log`: 730 gün
- `customer_inactive`: 1095 gün

## accounts — veri öznesi: kullanıcı

| Model.Alan | Kategori | Özel nitelikli | Şifreli | Güven | Amaç | Hukuki dayanak |
|---|---|---|---|---|---|---|
| `ApprovalRequest.review_note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `LoginAttempt.ip_address` | çevrimiçi tanımlayıcı | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `LoginAttempt.user_agent` | çevrimiçi tanımlayıcı | hayır | — | medium | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.display_name` | kimlik | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.email` | iletişim | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.first_name` | kimlik | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.last_name` | kimlik | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.notes` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.password` | kimlik doğrulama | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.password_changed_at` | kimlik doğrulama | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.phone` | iletişim | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `User.pin_hash` | kimlik doğrulama | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |

## aiservices — veri öznesi: kullanıcı

| Model.Alan | Kategori | Özel nitelikli | Şifreli | Güven | Amaç | Hukuki dayanak |
|---|---|---|---|---|---|---|
| `AISuggestion.review_note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `ProviderPricing.source_note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |

## core — veri öznesi: kullanıcı

| Model.Alan | Kategori | Özel nitelikli | Şifreli | Güven | Amaç | Hukuki dayanak |
|---|---|---|---|---|---|---|
| `AppSetting.secret_value` | kimlik doğrulama | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `AuditLog.ip_address` | çevrimiçi tanımlayıcı | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `AuditLog.user_agent` | çevrimiçi tanımlayıcı | hayır | — | medium | REVIEW_REQUIRED | REVIEW_REQUIRED |

## crm — veri öznesi: müşteri

| Model.Alan | Kategori | Özel nitelikli | Şifreli | Güven | Amaç | Hukuki dayanak |
|---|---|---|---|---|---|---|
| `ConsentRecord.note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.allergy_notes` | sağlık adayı | ⚠️ evet | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.birth_date` | kimlik (doğum) | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.birth_day` | kimlik (doğum) | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.birth_month` | kimlik (doğum) | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.blacklist_reason` | davranış/değerlendirme | hayır | — | medium | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.dietary_notes` | sağlık adayı | ⚠️ evet | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.email` | iletişim | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.email_index` | iletişim | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.first_name` | kimlik | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.last_name` | kimlik | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.notes` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.phone` | iletişim | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.phone_index` | iletişim | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Customer.segment` | davranış/tercih | hayır | — | medium | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `CustomerVisitNote.note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `DataErasureRequest.retained_records_note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `LoyaltyAccount.card_number` | finansal | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `LoyaltyTransaction.note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |

## hr — veri öznesi: personel

| Model.Alan | Kategori | Özel nitelikli | Şifreli | Güven | Amaç | Hukuki dayanak |
|---|---|---|---|---|---|---|
| `Employee.address` | iletişim (adres) | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.email` | iletişim | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.emergency_contact` | iletişim (acil durum) | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.first_name` | kimlik | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.hourly_rate` | finansal (ücret) | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.iban` | finansal | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.last_name` | kimlik | hayır | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.national_id` | kimlik (resmî numara) | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.notes` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Employee.phone` | iletişim | hayır | ✅ | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `EmployeeTrainingRecord.notes` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `LeaveRequest.review_note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Shift.notes` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `ShiftAssignment.note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |

## operations — veri öznesi: misafir/müşteri

| Model.Alan | Kategori | Özel nitelikli | Şifreli | Güven | Amaç | Hukuki dayanak |
|---|---|---|---|---|---|---|
| `BusinessDay.notes` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Order.notes` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `PrepTicket.note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `Reservation.allergy_notes` | sağlık adayı | ⚠️ evet | — | high | REVIEW_REQUIRED | REVIEW_REQUIRED |
| `WaitlistEntry.note` | serbest metin (PII içerebilir) | hayır | — | low | REVIEW_REQUIRED | REVIEW_REQUIRED |

## ⚠️ Özel nitelikli veri adayları (KVKK m.6 / GDPR m.9 ön işareti)

- `crm.Customer.allergy_notes` — sağlık adayı (Alerji notları)
- `crm.Customer.dietary_notes` — sağlık adayı (Beslenme tercihleri)
- `operations.Reservation.allergy_notes` — sağlık adayı (Alerji notları)

Bu alanlar için açık rıza/istisna değerlendirmesi ve ek güvenlik
önlemi incelemesi zorunludur.

