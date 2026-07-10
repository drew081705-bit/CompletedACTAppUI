import unittest

import app as app_module


class AttendanceToggleTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        app_module.students.clear()
        app_module.students["Jeff"] = {"present": True, "class": "Yellow"}

    def test_toggle_attendance_flips_presence_and_updates_state(self):
        first_response = self.client.post("/api/toggle_attendance", json={"name": "Jeff"})
        self.assertEqual(first_response.status_code, 200)

        first_payload = first_response.get_json()
        self.assertFalse(first_payload["state"]["students"]["Jeff"]["present"])
        self.assertIn("absent", first_payload["message"].lower())

        second_response = self.client.post("/api/toggle_attendance", json={"name": "Jeff"})
        self.assertEqual(second_response.status_code, 200)

        second_payload = second_response.get_json()
        self.assertTrue(second_payload["state"]["students"]["Jeff"]["present"])
        self.assertIn("present", second_payload["message"].lower())


if __name__ == "__main__":
    unittest.main()
