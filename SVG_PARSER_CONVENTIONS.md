# SVG Parser - Form Field Conventions

This SVG parser converts SVG text elements into form fields based on their ID attributes.

## Basic Field Types

### Text Input
```xml
<text id="fieldname.text">Default text here</text>
```
**Examples:**
```xml
<text id="company_name.text">Enter company name</text>
<text id="phone_number.text">Enter phone number</text>
```

### Textarea (Multi-line)
```xml
<text id="fieldname.textarea">Default text here</text>
```
**Examples:**
```xml
<text id="description.textarea">Enter description</text>
<text id="address.textarea">Enter full address</text>
```

## Field Extensions

### Random Code Generation (.gen)
```xml
<text id="fieldname.gen.max_12">Generated code will appear here</text>
```
- Creates random alphanumeric code
- `.max_12` = 12 characters long

**Examples:**
```xml
<text id="reference_code.gen.max_8">REF12345</text>
<text id="order_number.gen.max_10">ORD98765432</text>
```

### Character Limit (.max)
```xml
<text id="fieldname.text.max_50">Enter text (max 50 chars)</text>
<text id="fieldname.textarea.max_200">Enter text (max 200 chars)</text>
```

### Dropdown Options (.select)
```xml
<text id="fieldname.select_option1">Option 1 Name</text>
<text id="fieldname.select_option2">Option 2 Name</text>
```
All elements with same base ID + `.select_` become one dropdown.

**Examples:**
```xml
<text id="country.select_usa">United States</text>
<text id="country.select_canada">Canada</text>
<text id="country.select_uk">United Kingdom</text>
```

### Field Sync (.depends)
```xml
<text id="fieldname.text.depends_ANOTHER_ID">This field will sync with ANOTHER_ID</text>
```
When `ANOTHER_ID` changes, this field copies the same value.

**Examples:**
```xml
<text id="company_name.text">Enter company name</text>
<text id="company_display.text.depends_company_name">Will show same as company name</text>
```

### Tracking ID with Link
```xml
<text id="Tracking_ID.gen.max_10.link_https://example.com">Generated tracking code</text>
```
- Must use exact name: `Tracking_ID` (uppercase)
- Generates random code
- Adds clickable link

**Examples:**
```xml
<text id="Tracking_ID.gen.max_8.link_https://track.example.com">TRK12345</text>
<text id="Tracking_ID.gen.max_12.link_https://orders.example.com">TRK123456789</text>
```

## Examples

### Simple Form
```xml
<text id="company_name.text">Enter company name</text>
<text id="description.textarea.max_300">Company description</text>
<text id="Tracking_ID.gen.max_8.link_https://track.example.com">TRK12345</text>
```

### Form with Sync Fields
```xml
<text id="full_name.text">Enter full name</text>
<text id="display_name.text.depends_full_name">Will show same as full name</text>
```

### Form with Dropdown
```xml
<text id="country.select_usa">United States</text>
<text id="country.select_canada">Canada</text>
<text id="country.select_uk">United Kingdom</text>
```

## Quick Reference

| Extension | What it does | Example |
|-----------|-------------|---------|
| `.text` | Single-line text | `id="name.text"` |
| `.textarea` | Multi-line text | `id="description.textarea"` |
| `.gen.max_N` | Random code (N chars) | `id="code.gen.max_8"` |
| `.max_N` | Character limit | `id="title.text.max_100"` |
| `.select_OPTION` | Dropdown option | `id="country.select_usa"` |
| `.depends_FIELD` | Sync with field | `id="confirm.text.depends_email"` |
| `Tracking_ID.gen.max_N.link_URL` | Tracking code with link | `id="Tracking_ID.gen.max_8.link_https://..."` |

## Important Notes

- Use `Tracking_ID` (uppercase) for tracking codes with links
- All other field names should be lowercase with underscores
- The parser converts SVG text elements into form fields automatically
