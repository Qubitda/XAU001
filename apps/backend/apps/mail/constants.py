"""Canonical transactional template keys."""

WELCOME = "welcome"
PAYMENT_SUCCESS = "payment_success"
PAYMENT_FAILED = "payment_failed"
PAYMENT_REFUNDED = "payment_refunded"
BANK_TRANSFER_PENDING = "bank_transfer_pending"
ORDER_CANCELLED = "order_cancelled"
ORDER_CREATED = "order_created"
PASSWORD_RESET = "password_reset"
EMAIL_VERIFICATION = "email_verification"
CART_RECOVERY_B2C_T1 = "cart_recovery_b2c_t1"
CART_RECOVERY_B2C_T3 = "cart_recovery_b2c_t3"
CART_RECOVERY_B2B_T1 = "cart_recovery_b2b_t1"
CART_RECOVERY_B2B_T2 = "cart_recovery_b2b_t2"

FILESYSTEM_TEMPLATE_KEYS = frozenset(
    {
        WELCOME,
        PAYMENT_SUCCESS,
        PAYMENT_FAILED,
        PAYMENT_REFUNDED,
        BANK_TRANSFER_PENDING,
        ORDER_CANCELLED,
        ORDER_CREATED,
        PASSWORD_RESET,
        EMAIL_VERIFICATION,
        CART_RECOVERY_B2C_T1,
        CART_RECOVERY_B2C_T3,
        CART_RECOVERY_B2B_T1,
        CART_RECOVERY_B2B_T2,
    }
)

DEFAULT_SUBJECTS = {
    WELCOME: "Tara Gold — Hoş geldiniz",
    PAYMENT_SUCCESS: "Tara Gold — Ödemeniz alındı ({{ order_no }})",
    PAYMENT_FAILED: "Tara Gold — Ödeme tamamlanamadı ({{ order_no }})",
    PAYMENT_REFUNDED: "Tara Gold — İade / iptal bilgilendirmesi ({{ order_no }})",
    BANK_TRANSFER_PENDING: "Tara Gold — Havale bilgileri ({{ order_no }})",
    ORDER_CANCELLED: "Tara Gold — Sipariş iptal edildi ({{ order_no }})",
    ORDER_CREATED: "Tara Gold — Siparişiniz alındı ({{ order_no }})",
    PASSWORD_RESET: "Tara Gold — Parola sıfırlama",
    EMAIL_VERIFICATION: "Tara Gold — E-posta doğrulama",
    CART_RECOVERY_B2C_T1: "Tara Diamond — Sepetiniz sizi bekliyor",
    CART_RECOVERY_B2C_T3: "Tara Diamond — Sepetinizdeki tasarımlar hâlâ sizin",
    CART_RECOVERY_B2B_T1: "Tara Diamond — Taslak sipariş fişiniz hazır — {{ org_name }}",
    CART_RECOVERY_B2B_T2: "Tara Diamond — {{ org_name }} taslak fişi: kur, stok ve vade notları",
}
