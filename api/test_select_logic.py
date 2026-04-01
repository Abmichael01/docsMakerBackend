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
        
        # value = SVG text content, label = the select_ suffix
        options = status_field['options']
        self.assertEqual(options[0]['value'], 'Processing')
        self.assertEqual(options[0]['label'], 'proc')
        self.assertEqual(options[1]['value'], 'Shipped')
        self.assertEqual(options[1]['label'], 'ship')
        
        # currentValue = text content of the visible option ('Processing')
        self.assertEqual(status_field['currentValue'], 'Processing')

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

class SelectEditableTrackTest(unittest.TestCase):
    """Regression tests: .editable and .track_ROLE on select options must propagate to the parent field."""

    def _parse(self, svg):
        fields = parse_svg_to_form_fields(svg)
        return next((f for f in fields if f['id'] == 'Status'), None)

    def test_editable_on_first_option(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <text id="Status.select_In_Transit.editable">In Transit</text>
          <text id="Status.select_Delivered">Delivered</text>
          <text id="Status.select_Error">Error</text>
        </svg>'''
        f = self._parse(svg)
        self.assertTrue(f.get('editable'), "editable must propagate from first option")

    def test_editable_on_last_option(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <text id="Status.select_In_Transit">In Transit</text>
          <text id="Status.select_Delivered">Delivered</text>
          <text id="Status.select_Error.editable">Error</text>
        </svg>'''
        f = self._parse(svg)
        self.assertTrue(f.get('editable'), "editable must propagate from last option")

    def test_track_on_any_option(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <text id="Status.select_In_Transit">In Transit</text>
          <text id="Status.select_Error.track_status">Error</text>
        </svg>'''
        f = self._parse(svg)
        self.assertEqual(f.get('trackingRole'), 'status', "trackingRole must propagate from option with .track_status")

    def test_editable_and_track_on_different_options(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <text id="Status.select_In_Transit.editable">In Transit</text>
          <text id="Status.select_Delivered">Delivered</text>
          <text id="Status.select_Error.track_status">Error</text>
        </svg>'''
        f = self._parse(svg)
        self.assertTrue(f.get('editable'), "editable must survive when track_ is on a different option")
        self.assertEqual(f.get('trackingRole'), 'status', "trackingRole must survive when editable is on a different option")

    def test_no_modifiers_stays_not_editable(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <text id="Status.select_In_Transit">In Transit</text>
          <text id="Status.select_Error">Error</text>
        </svg>'''
        f = self._parse(svg)
        self.assertFalse(f.get('editable'), "editable must stay False when no option carries it")

    def test_editable_and_track_on_same_option(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg">
          <text id="Status.select_In_Transit">In Transit</text>
          <text id="Status.select_Error.editable.track_status">Error</text>
        </svg>'''
        f = self._parse(svg)
        self.assertTrue(f.get('editable'), "editable must propagate when combined with track_ on same option")
        self.assertEqual(f.get('trackingRole'), 'status', "trackingRole must propagate when combined with editable on same option")


if __name__ == '__main__':
    unittest.main()
