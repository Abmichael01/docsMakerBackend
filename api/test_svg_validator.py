from django.test import SimpleTestCase
from api.svg_validator import validate_svg_id


class GrayscaleOnDependsFieldTests(SimpleTestCase):
    """validate_svg_id must accept .grayscale after .depends_"""

    def test_depends_grayscale(self):
        valid, err = validate_svg_id("Copy.depends_Photo.grayscale")
        self.assertTrue(valid, err)

    def test_depends_grayscale_intensity(self):
        valid, err = validate_svg_id("Copy.depends_Photo.grayscale_50")
        self.assertTrue(valid, err)

    def test_depends_grayscale_then_track(self):
        valid, err = validate_svg_id("Copy.depends_Photo.grayscale.track_name")
        self.assertTrue(valid, err)

    def test_depends_grayscale_intensity_then_track(self):
        valid, err = validate_svg_id("Copy.depends_Photo.grayscale_50.track_name")
        self.assertTrue(valid, err)

    def test_depends_without_grayscale_still_valid(self):
        valid, err = validate_svg_id("Copy.depends_Photo")
        self.assertTrue(valid, err)

    def test_grayscale_before_depends_is_invalid(self):
        """grayscale must come AFTER depends_, not before"""
        valid, _ = validate_svg_id("Copy.grayscale.depends_Photo")
        self.assertFalse(valid)
