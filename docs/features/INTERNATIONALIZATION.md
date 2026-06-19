# Internationalization (i18n) Module

## Supported Languages
| Language | Code | Status |
|----------|------|--------|
| English | en | ✅ Complete |
| Myanmar (Burmese) | my | ✅ Complete |
| Thai | th | 🔄 v1.1.0 |
| Vietnamese | vi | 🔄 v1.1.0 |
| Chinese (Simplified) | zh-CN | 🔄 v1.2.0 |
| Japanese | ja | 🔄 v1.2.0 |

## Implementation

### Backend
```python
from fastapi_babel import Babel

babel = Babel(default_locale='en')

@app.get("/api/v1/products")
def get_products(locale: str = 'en'):
    return {
        "message": babel._("products_list"),
        "data": [...]
    }
```

### Frontend
```typescript
import { useTranslation } from 'react-i18next';

function ProductList() {
  const { t } = useTranslation();
  return <h1>{t('products.title')}</h1>;
}
```

### Translation Files
```
frontend/src/i18n/
├── en/
│   ├── common.json
│   ├── products.json
│   └── orders.json
├── my/
│   ├── common.json
│   ├── products.json
│   └── orders.json
└── th/
    ├── common.json
    ├── products.json
    └── orders.json
```

## Adding a New Language
1. Create translation files in `frontend/src/i18n/[lang]/`
2. Add backend translations in `backend/app/i18n/`
3. Update language selector in UI
4. Test with native speakers
