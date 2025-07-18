#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import shutil
import uuid
from pathlib import Path

from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QTextEdit, QFileDialog,
    QMessageBox, QCheckBox, QProgressBar, QLabel
)

# ----------------------
# File categories: extension -> folder name
FILE_CATEGORIES = {
    "Images": {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "svg"},
    "Videos": {"mp4", "mkv", "avi", "mov", "wmv", "flv"},
    "Audio": {"mp3", "wav", "aac", "flac", "ogg"},
    "Documents": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md"},
    "Archives": {"zip", "rar", "7z", "tar", "gz"},
}


def categorize(filename: str) -> str:
    """Return category name based on file extension."""
    ext = Path(filename).suffix.lower().lstrip(".")
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return "Others"


def ensure_directory(path: Path):
    """Create directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def unique_filename(directory: Path, name: str) -> str:
    """
    If `directory/name` exists, append a short UUID to the base filename.
    This prevents silent overwrites.
    """
    target = directory / name
    if not target.exists():
        return name

    stem = Path(name).stem
    suffix = Path(name).suffix
    new_name = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
    return new_name


# ----------------------
# Worker runs in background thread
class OrganizerWorker(QObject):
    progress_updated = pyqtSignal(int)     # emits percentage 0-100
    log_updated = pyqtSignal(str)          # emits a log line
    work_finished = pyqtSignal()           # emits when done

    def __init__(self, sources: list, destination: str, move_files: bool):
        super().__init__()
        self.sources = sources
        self.destination = Path(destination)
        self.move_files = move_files

    def run(self):
        # Gather all files first
        file_list = []
        for src in self.sources:
            for path in Path(src).rglob("*"):
                if path.is_file():
                    file_list.append(path)

        total_files = len(file_list)
        if total_files == 0:
            self.log_updated.emit("⚠️ No files found. Aborting.")
            self.work_finished.emit()
            return

        processed = 0
        for file_path in file_list:
            try:
                category = categorize(file_path.name)
                target_folder = self.destination / category
                ensure_directory(target_folder)

                safe_name = unique_filename(target_folder, file_path.name)
                target_path = target_folder / safe_name

                if self.move_files:
                    shutil.move(str(file_path), str(target_path))
                    action = "Moved"
                else:
                    shutil.copy2(str(file_path), str(target_path))
                    action = "Copied"

                self.log_updated.emit(f"{action}: {file_path} → {target_path}")
            except Exception as e:
                self.log_updated.emit(f"❌ Error processing {file_path}: {e}")

            processed += 1
            pct = int(processed / total_files * 100)
            self.progress_updated.emit(pct)

        self.work_finished.emit()


# ----------------------
# Main application GUI
class FileOrganizerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🗂️ Secure File Organizer")
        self.resize(720, 600)
        self._setup_ui()
        self._connect_signals()

        self.worker_thread = None
        self.worker = None

    def _setup_ui(self):
        """Builds the UI layout."""
        main_layout = QVBoxLayout(self)

        # 1. Source folders
        lbl_sources = QLabel("Source Folders:")
        self.list_sources = QListWidget()
        btn_add_source = QPushButton("➕ Add Source")
        btn_remove_source = QPushButton("➖ Remove Selected")
        h_src_buttons = QHBoxLayout()
        h_src_buttons.addWidget(btn_add_source)
        h_src_buttons.addWidget(btn_remove_source)
        main_layout.addWidget(lbl_sources)
        main_layout.addLayout(h_src_buttons)
        main_layout.addWidget(self.list_sources)

        # 2. Destination
        lbl_dest = QLabel("Destination Folder:")
        self.lbl_dest_display = QLabel("<Not Chosen>")
        btn_choose_dest = QPushButton("📁 Choose Destination")
        h_dest = QHBoxLayout()
        h_dest.addWidget(self.lbl_dest_display, 1)
        h_dest.addWidget(btn_choose_dest)
        main_layout.addWidget(lbl_dest)
        main_layout.addLayout(h_dest)

        # 3. Move vs Copy
        self.chk_move = QCheckBox("Move files (unchecked = Copy)")
        self.chk_move.setChecked(True)
        main_layout.addWidget(self.chk_move)

        # 4. Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # 5. Log output
        lbl_log = QLabel("Operation Log:")
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        main_layout.addWidget(lbl_log)
        main_layout.addWidget(self.txt_log, stretch=2)

        # 6. Start button
        self.btn_start = QPushButton("🚀 Start Organizing")
        main_layout.addWidget(self.btn_start)

        # expose buttons
        self.btn_add_source = btn_add_source
        self.btn_remove_source = btn_remove_source
        self.btn_choose_dest = btn_choose_dest

        # Basic styling
        style = """
            QPushButton {
                font-size: 14px;
                padding: 8px 16px;
                background: #007ACC;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #005F9E;
            }
            QListWidget, QTextEdit {
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
            }
        """
        self.setStyleSheet(style)

    def _connect_signals(self):
        self.btn_add_source.clicked.connect(self.on_add_source)
        self.btn_remove_source.clicked.connect(self.on_remove_source)
        self.btn_choose_dest.clicked.connect(self.on_choose_destination)
        self.btn_start.clicked.connect(self.on_start)

    def on_add_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", str(Path.home()))
        if folder and not any(self.list_sources.item(i).text() == folder
                              for i in range(self.list_sources.count())):
            self.list_sources.addItem(folder)

    def on_remove_source(self):
        for item in self.list_sources.selectedItems():
            self.list_sources.takeItem(self.list_sources.row(item))

    def on_choose_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder", str(Path.home()))
        if folder:
            self.lbl_dest_display.setText(folder)

    def log(self, message: str):
        """Append a line to the log window."""
        self.txt_log.append(message)
        self.txt_log.verticalScrollBar().setValue(
            self.txt_log.verticalScrollBar().maximum()
        )

    def on_start(self):
        """Validate input, disable UI, and launch worker thread."""
        sources = [self.list_sources.item(i).text() for i in range(self.list_sources.count())]
        destination = self.lbl_dest_display.text()
        move_files = self.chk_move.isChecked()

        if not sources:
            QMessageBox.warning(self, "Warning", "Please add at least one source folder.")
            return
        if destination == "<Not Chosen>":
            QMessageBox.warning(self, "Warning", "Please choose a destination folder.")
            return

        # Disable UI controls
        self.btn_start.setEnabled(False)
        self.btn_add_source.setEnabled(False)
        self.btn_remove_source.setEnabled(False)
        self.btn_choose_dest.setEnabled(False)

        self.txt_log.clear()
        self.progress_bar.setValue(0)
        self.log("🔹 Starting operation...")

        # Setup worker + thread
        self.worker = OrganizerWorker(sources, destination, move_files)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        # Connect signals
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.log_updated.connect(self.log)
        self.worker.work_finished.connect(self.on_finished)
        self.worker.work_finished.connect(self.worker_thread.quit)
        self.worker.work_finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        # Start
        self.worker_thread.start()

    def on_finished(self):
        """Re-enable UI and notify user."""
        self.log("✅ Operation completed.")
        QMessageBox.information(self, "Done", "All files have been organized.")
        self.btn_start.setEnabled(True)
        self.btn_add_source.setEnabled(True)
        self.btn_remove_source.setEnabled(True)
        self.btn_choose_dest.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    window = FileOrganizerApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
