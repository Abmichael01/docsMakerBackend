# Date Format Extension - Complete Examples

## Basic Usage

### Simple Date Field
```xml
<text id="birth_date.date">2025-01-10</text>
```
**Result:** Shows date picker, stores as `2025-01-10`

---

## Date Format Examples

### Common Formats
```xml
<!-- US Format -->
<text id="Date_of_Birth.date_MM/DD/YYYY">01/10/2025</text>

<!-- Short Format -->
<text id="Event_Date.date_MMM_DD">Jan 10</text>

<!-- Full Format -->
<text id="Created_Date.date_MMMM_D,_YYYY">January 10, 2025</text>

<!-- European Format -->
<text id="Expiry_Date.date_DD/MM/YYYY">10/01/2025</text>

<!-- ISO-like Format -->
<text id="Start_Date.date_YYYY-MM-DD">2025-01-10</text>
```

### With Time
```xml
<text id="Timestamp.date_MM/DD/YYYY_HH:mm">01/10/2025 14:30</text>
<text id="Created_At.date_MMM_DD,_YYYY_h:mm_A">Jan 10, 2025 2:30 PM</text>
<text id="Updated.date_YYYY-MM-DD_HH:mm:ss">2025-01-10 14:30:45</text>
```

---

## Combined with Other Extensions

### Date + Editable
```xml
<text id="Delivery_Date.date_MM/DD/YYYY.editable">01/15/2025</text>
```
**Result:** User can edit date even after purchase

### Date + Tracking Role
```xml
<text id="Event_Date.date_MMM_DD.track_event_date">Jan 10</text>
```
**Result:** Date formatted as "Jan 10", tracked for external display

### Date + Depends (Field Sync)
```xml
<text id="Start_Date.date_MM/DD/YYYY">01/10/2025</text>
<text id="Confirm_Start.date_MM/DD/YYYY.depends_Start_Date">01/10/2025</text>
```
**Result:** Confirm_Start automatically copies Start_Date value

### Date + Editable + Tracking
```xml
<text id="Delivery_Date.date_MM/DD/YYYY.editable.track_delivery">01/15/2025</text>
```
**Result:** Editable date with tracking role (track_ must be last!)

### Full Example with All Extensions
```xml
<text id="Expected_Delivery.date_MMMM_D,_YYYY.editable.track_expected_date">January 15, 2025</text>
```
**Result:** 
- Format: "January 15, 2025"
- Editable after purchase
- Tracked as `expected_date` role
- All extensions work together perfectly!

---

## Real-World Examples

### Tracking Document
```xml
<text id="Tracking_ID.gen.max_12.tracking_id.link_https://track.example.com">TRK123456789</text>
<text id="Customer_Name.text.track_name">John Doe</text>
<text id="Order_Date.date_MMM_DD,_YYYY.track_order_date">Jan 10, 2025</text>
<text id="Expected_Delivery.date_MM/DD/YYYY.editable.track_delivery_date">01/15/2025</text>
<text id="Status.select_Processing">Processing</text>
<text id="Status.select_Shipped.editable.track_status">Shipped</text>
<text id="Status.select_Delivered.editable.track_status">Delivered</text>
```

### Invoice with Dates
```xml
<text id="Invoice_Number.gen.max_10">INV1234567890</text>
<text id="Issue_Date.date_MM/DD/YYYY">01/10/2025</text>
<text id="Due_Date.date_MMMM_D,_YYYY">January 25, 2025</text>
<text id="Payment_Date.date_MM/DD/YYYY.editable">01/20/2025</text>
```

### Certificate with Multiple Date Formats
```xml
<text id="Student_Name.text">Jane Smith</text>
<text id="Course_Name.text">Advanced React Development</text>
<text id="Completion_Date.date_MMMM_DD,_YYYY">January 10, 2025</text>
<text id="Issue_Date.date_MM/DD/YYYY">01/10/2025</text>
<text id="Valid_Until.date_MMM_YYYY">Jan 2027</text>
```

---

## Format Code Reference

| Code | Output | Example |
|------|--------|---------|
| `YYYY` | Full year | 2025 |
| `YY` | Short year | 25 |
| `MMMM` | Full month | January |
| `MMM` | Short month | Jan |
| `MM` | Month (zero-padded) | 01 |
| `M` | Month (no padding) | 1 |
| `DD` | Day (zero-padded) | 10 |
| `D` | Day (no padding) | 10 |
| `dddd` | Full weekday | Monday |
| `ddd` | Short weekday | Mon |
| `HH` | Hour 24 (padded) | 14 |
| `H` | Hour 24 (no pad) | 14 |
| `hh` | Hour 12 (padded) | 02 |
| `h` | Hour 12 (no pad) | 2 |
| `mm` | Minutes (padded) | 05 |
| `m` | Minutes (no pad) | 5 |
| `ss` | Seconds (padded) | 07 |
| `s` | Seconds (no pad) | 7 |
| `A` | AM/PM uppercase | PM |
| `a` | am/pm lowercase | pm |

---

## Important Notes

✅ `.date_FORMAT` works with `.editable`, `.track_`, `.depends_`  
✅ Date picker stores date in YYYY-MM-DD internally  
✅ Display format is applied when rendering SVG  
✅ Format string can include any separator (`/`, `-`, `,`, spaces, etc.)  
✅ Underscores in extension are converted to slashes (e.g., `date_MM_DD_YYYY` → `MM/DD/YYYY`)  

⚠️ If using `.track_`, it must still be the LAST extension:
- ✅ `field.date_MM/DD/YYYY.editable.track_date`
- ❌ `field.date_MM/DD/YYYY.track_date.editable`


