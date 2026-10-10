"""
Unit tests for Document, Stroke, Vector Eraser, Undo/Redo, and File Export.
"""

import sys
import os
import tempfile
import unittest

from PyQt5.QtWidgets import QApplication

# Ensure QApplication exists for QImage / QPainter tests
_app = QApplication.instance() or QApplication(sys.argv)

from drawing.document import Document
from drawing.stroke import Stroke, ToolType


class TestDocument(unittest.TestCase):
    def setUp(self):
        self.doc = Document()

    def test_stroke_creation_and_finish(self):
        self.doc.start_stroke(ToolType.PEN, "#2563EB", 6.0, 0.1, 0.1)
        self.doc.add_point_to_active(0.2, 0.2)
        self.doc.add_point_to_active(0.3, 0.3)
        self.assertEqual(len(self.doc.strokes), 0)  # Active stroke not yet committed
        
        finished = self.doc.finish_stroke()
        self.assertIsNotNone(finished)
        self.assertEqual(len(self.doc.strokes), 1)
        self.assertEqual(self.doc.strokes[0].point_count(), 3)
        self.assertTrue(self.doc.can_undo())

    def test_undo_and_redo_stroke(self):
        self.doc.start_stroke(ToolType.PEN, "#EF4444", 4.0, 0.1, 0.1)
        self.doc.add_point_to_active(0.5, 0.5)
        self.doc.finish_stroke()
        self.assertEqual(len(self.doc.strokes), 1)

        # Undo
        self.assertTrue(self.doc.undo())
        self.assertEqual(len(self.doc.strokes), 0)
        self.assertTrue(self.doc.can_redo())

        # Redo
        self.assertTrue(self.doc.redo())
        self.assertEqual(len(self.doc.strokes), 1)
        self.assertEqual(self.doc.strokes[0].color, "#EF4444")

    def test_vector_eraser_and_undo(self):
        # Create a stroke passing through (0.5, 0.5)
        self.doc.start_stroke(ToolType.PEN, "#000000", 6.0, 0.4, 0.4)
        self.doc.add_point_to_active(0.6, 0.6)
        self.doc.finish_stroke()
        self.assertEqual(len(self.doc.strokes), 1)

        # Erase at (0.5, 0.5) with radius 0.1
        count = self.doc.erase_at(0.5, 0.5, radius=0.1)
        self.assertEqual(count, 1)
        self.assertEqual(len(self.doc.strokes), 0)

        # Undo eraser must restore the erased stroke
        self.assertTrue(self.doc.undo())
        self.assertEqual(len(self.doc.strokes), 1)

    def test_clear_canvas_and_undo(self):
        self.doc.start_stroke(ToolType.PEN, "#10B981", 6.0, 0.1, 0.1)
        self.doc.finish_stroke()
        self.doc.start_stroke(ToolType.PEN, "#F59E0B", 6.0, 0.2, 0.2)
        self.doc.finish_stroke()
        self.assertEqual(len(self.doc.strokes), 2)

        self.doc.clear()
        self.assertEqual(len(self.doc.strokes), 0)

        self.assertTrue(self.doc.undo())
        self.assertEqual(len(self.doc.strokes), 2)

    def test_png_export(self):
        self.doc.start_stroke(ToolType.PEN, "#2563EB", 10.0, 0.2, 0.2)
        self.doc.add_point_to_active(0.8, 0.8)
        self.doc.finish_stroke()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            ok = self.doc.export_to_png(tmp_path, width=800, height=450)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(tmp_path))
            self.assertGreater(os.path.getsize(tmp_path), 500)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_json_project_persistence(self):
        self.doc.start_stroke(ToolType.PEN, "#7C3AED", 8.0, 0.25, 0.25)
        self.doc.add_point_to_active(0.75, 0.75)
        self.doc.finish_stroke()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            saved = self.doc.save_to_file(tmp_path)
            self.assertTrue(saved)

            new_doc = Document()
            loaded = new_doc.load_from_file(tmp_path)
            self.assertTrue(loaded)
            self.assertEqual(len(new_doc.strokes), 1)
            self.assertEqual(new_doc.strokes[0].color, "#7C3AED")
            self.assertEqual(new_doc.strokes[0].thickness, 8.0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
