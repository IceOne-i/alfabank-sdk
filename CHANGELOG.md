# Changelog

## [Unreleased]

### Added
- `AlfaBankClient` — async-клиент Alfa API (h2h): выписки, сводка оборотов, customer-info.
- Две схемы аутентификации (`ApiKey`, `Bearer`) + `token_provider` для внешнего управления токенами.
- Экспериментальный модуль `alfabank.oauth` (обмен кода, refresh, кэширующий провайдер).
- Идемпотентные ретраи с backoff, опциональный rate limiter, маппинг ошибок API.
- Модели pydantic v2 с `Decimal` для денежных сумм; проверены на моках банка.
