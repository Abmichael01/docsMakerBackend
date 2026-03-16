import unittest
import xml.etree.ElementTree as ET
from api.svg_parser import parse_svg_to_form_fields, create_select_option
from api.svg_updater import update_svg_from_field_updates

class SelectLogicTest(unittest.TestCase):
    def test_select_parsing(self):
        svg = """
        <svg>
            <text id="Status.select_proc">Processing</text>
            <text id="Status.select_ship" opacity="0">Shipped</text>
            <text id="Status.select_del" visibility="hidden">Delivered</text>
            <text id="Status" y="10">Fallback Text</text>
        </svg>
        """
        fields = parse_svg_to_form_fields(svg)
        status_field = next(f for f in fields if f['id'] == 'Status')
        
        self.assertEqual(status_field['type'], 'select')
        self.assertEqual(len(status_field['options']), 3)
        
        # Check values and labels
        options = status_field['options']
        self.assertEqual(options[0]['value'], 'proc')
        self.assertEqual(options[0]['label'], 'Processing')
        self.assertEqual(options[1]['value'], 'ship')
        self.assertEqual(options[1]['label'], 'Shipped')
        
        # Check initial value (should be 'proc' because it's visible)
        self.assertEqual(status_field['currentValue'], 'proc')

    def test_select_update(self):
        form_fields = [{
            'id': 'Status',
            'type': 'select',
            'options': [
                {'value': 'proc', 'label': 'Processing', 'svgElementId': 'Status.select_proc', 'displayText': 'Processing'},
                {'value': 'ship', 'label': 'Shipped', 'svgElementId': 'Status.select_ship', 'displayText': 'Shipped'}
            ],
            'currentValue': 'proc'
        }]
        
        svg = """
        <svg>
            <text id="Status.select_proc">Processing</text>
            <text id="Status.select_ship" opacity="0">Shipped</text>
            <text id="Status.text" y="10">Current Status</text>
        </svg>
        """
        
        # Update to Shipped
        updates = [{'id': 'Status', 'value': 'ship'}]
        updated_svg, updated_fields = update_svg_from_field_updates(svg, form_fields, updates)
        
        # Verify visibility
        root = ET.fromstring(updated_svg)
        proc_el = root.find(".//*[@id='Status.select_proc']")
        ship_el = root.find(".//*[@id='Status.select_ship']")
        text_el = root.find(".//*[@id='Status.text']")
        
        self.assertEqual(proc_el.get('display'), 'none')
        self.assertEqual(ship_el.get('visibility'), 'visible')
        self.assertIsNone(ship_el.get('display'))
        
        # Verify text injection (uses Label/DisplayText)
        self.assertEqual(text_el.text, 'Shipped')

if __name__ == '__main__':
    unittest.main()
