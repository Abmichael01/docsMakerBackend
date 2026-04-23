from django.test import SimpleTestCase

from .utils import build_source_label, classify_referrer, derive_channel_group, normalize_attribution


class AttributionUtilsTests(SimpleTestCase):
    def test_direct_traffic_defaults(self):
        attribution = normalize_attribution({})

        self.assertEqual(attribution["source"], "direct")
        self.assertEqual(attribution["medium"], "(none)")
        self.assertEqual(attribution["channel_group"], "Direct")

    def test_google_referrer_maps_to_organic_search(self):
        attribution = normalize_attribution({}, referrer="https://www.google.com/search?q=sharp")

        self.assertEqual(attribution["source"], "google")
        self.assertEqual(attribution["medium"], "organic")
        self.assertEqual(attribution["channel_group"], "Organic Search")

    def test_custom_source_defaults_to_custom_medium(self):
        attribution = normalize_attribution({
            "source": "facebook_ads",
            "is_custom_source": True,
        })

        self.assertEqual(attribution["source"], "facebook_ads")
        self.assertEqual(attribution["medium"], "custom")
        self.assertEqual(attribution["channel_group"], "Custom Campaign")

    def test_build_source_label_uses_source_and_medium(self):
        self.assertEqual(build_source_label("google", "organic"), "google / organic")

    def test_classify_referrer_for_social(self):
        classified = classify_referrer("https://www.instagram.com/sharptoolz/")

        self.assertEqual(classified["source"], "instagram")
        self.assertEqual(classified["medium"], "social")
        self.assertEqual(classified["channel_group"], "Organic Social")

    def test_channel_group_for_paid_search(self):
        self.assertEqual(derive_channel_group("google", "cpc"), "Paid Search")
