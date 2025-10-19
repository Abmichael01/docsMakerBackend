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

### File Upload
```xml
<text id="fieldname.upload">Upload file</text>
<text id="fieldname.file">Upload file</text>
```
**Examples:**
```xml
<text id="company_logo.upload">Upload company logo</text>
<text id="product_image.file">Upload product image</text>
<text id="document.upload">Upload document</text>
```

### Signature Field
```xml
<text id="fieldname.sign">Signature</text>
```
**Examples:**
```xml
<text id="author_signature.sign">Author Signature</text>
<text id="witness_signature.sign">Witness Signature</text>
<text id="approval_signature.sign">Approval Signature</text>
```

### Date Field
```xml
<text id="fieldname.date">2025-01-10</text>
```
Basic date picker (YYYY-MM-DD format).
**Examples:**
```xml
<text id="start_date.date">2025-01-10</text>
<text id="expiry_date.date">2025-12-31</text>
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

### Date Format (.date_FORMAT)
```xml
<text id="fieldname.date_MM/DD/YYYY">01/10/2025</text>
<text id="fieldname.date_MMM_DD">Jan 10</text>
```
Automatically formats dates based on specified format string.

**Format Codes:**
- `YYYY` - Full year (2025)
- `YY` - Short year (25)
- `MMMM` - Full month (January)
- `MMM` - Short month (Jan)
- `MM` - Month with zero (01)
- `M` - Month no zero (1)
- `DD` - Day with zero (01)
- `D` - Day no zero (1)
- `dddd` - Full weekday (Monday)
- `ddd` - Short weekday (Mon)
- `HH` - 24-hour with zero (01, 23)
- `H` - 24-hour no zero (1, 23)
- `hh` - 12-hour with zero (01, 12)
- `h` - 12-hour no zero (1, 12)
- `mm` - Minutes with zero (01, 59)
- `m` - Minutes no zero (1, 59)
- `ss` - Seconds with zero (01, 59)
- `s` - Seconds no zero (1, 59)
- `A` - AM/PM uppercase
- `a` - am/pm lowercase

**Examples:**
```xml
<text id="Date_of_Birth.date_MM/DD/YYYY">01/10/2025</text>
<text id="Event_Date.date_MMMM_D">January 10</text>
<text id="Created_At.date_MMM_DD,_YYYY">Jan 10, 2025</text>
<text id="Timestamp.date_MM/DD/YYYY_HH:mm">01/10/2025 14:30</text>
<text id="Delivery_Date.date_MMM_DD.editable.track_date">Jan 10</text>
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

### Tracking ID with Link (.tracking_id .link_)
```xml
<text id="Order_Number.gen.max_10.tracking_id.link_https://example.com">Generated tracking code</text>
```
- Use `.tracking_id` to mark field as tracking ID
- Use `.link_URL` to add clickable link
- Generates random code with `.gen.max_N`

**Examples:**
```xml
<text id="Order_Number.gen.max_8.tracking_id.link_https://track.example.com">TRK12345</text>
<text id="Booking_Ref.gen.max_12.tracking_id.link_https://orders.example.com">TRK123456789</text>
```

### Tracking Roles (.track_)
⚠️ **IMPORTANT: `.track_` extensions must ALWAYS be the LAST extension in the ID chain.**

```xml
<text id="fieldname.text.track_name">Customer Name</text>
<text id="fieldname.text.editable.track_status">Status</text>
```
- Maps fields to specific roles for tracking website display
- Must be the last extension (after `.gen`, `.max_`, `.link_`, `.editable`, etc.)
- Common roles: `track_name`, `track_email`, `track_status`, `track_destination`, `track_package`, `track_weight`, `track_error_message`

**Examples:**
```xml
<text id="Customer_Name.text.track_name">John Doe</text>
<text id="Customer_Email.email.track_email">john@example.com</text>
<text id="Destination.text.track_destination">123 Main St</text>
<text id="Status.select_Processing">Processing</text>
<text id="Status.select_Delivered.track_status">Delivered</text>
<text id="Status.select_Error.editable.track_status">Error</text>
```

### Editable After Purchase (.editable)
```xml
<text id="fieldname.text.editable">Editable text</text>
```
- Marks fields as editable even after document purchase
- By default, all fields become non-editable after purchase
- Must come BEFORE `.track_` extension if both are used

**Examples:**
```xml
<text id="Status.text.editable">Status field stays editable</text>
<text id="Notes.textarea.editable">Editable notes field</text>
<text id="Status.select_Processing">Processing</text>
<text id="Status.select_Delivered.editable.track_status">Delivered</text>
```

## Examples

### Simple Form
```xml
<text id="company_name.text">Enter company name</text>
<text id="description.textarea.max_300">Company description</text>
<text id="Order_Number.gen.max_8.tracking_id.link_https://track.example.com">TRK12345</text>
```

### Tracking Form with Editable Fields
```xml
<text id="Tracking_ID.gen.max_12.tracking_id.link_https://parcelfinda.com">TRK123456789</text>
<text id="Customer_Name.text.track_name">John Doe</text>
<text id="Customer_Email.email.track_email">john@example.com</text>
<text id="Destination.text.track_destination">123 Main St</text>
<text id="Status.select_Processing">Processing</text>
<text id="Status.select_In_Transit">In Transit</text>
<text id="Status.select_Delivered.editable.track_status">Delivered</text>
<text id="Status.select_Error">Error</text>
<text id="Error_Message.textarea.editable.track_error_message">Error details here</text>
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
| `.upload` | File upload field | `id="logo.upload"` |
| `.file` | File upload field | `id="document.file"` |
| `.sign` | Signature field | `id="signature.sign"` |
| `.gen.max_N` | Random code (N chars) | `id="code.gen.max_8"` |
| `.max_N` | Character limit | `id="title.text.max_100"` |
| `.date_FORMAT` | Date with format | `id="dob.date_MM/DD/YYYY"` |
| `.select_OPTION` | Dropdown option | `id="country.select_usa"` |
| `.depends_FIELD` | Sync with field | `id="confirm.text.depends_email"` |
| `.tracking_id` | Mark as tracking ID | `id="Order.gen.max_8.tracking_id"` |
| `.link_URL` | Add external link | `id="Order.tracking_id.link_https://..."` |
| `.editable` | Editable after purchase | `id="status.text.editable"` |
| `.track_ROLE` | Tracking role (MUST BE LAST) | `id="name.text.track_name"` |

## Important Notes

- ⚠️ **`.track_` extensions MUST ALWAYS be the LAST extension**
- If using both `.editable` and `.track_`, put `.editable` first: `field.text.editable.track_name`
- Use `.tracking_id` to mark the main tracking field
- All field names should use underscores for spaces
- The parser converts SVG text elements into form fields automatically
