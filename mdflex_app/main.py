#!/usr/bin/env python3
"""
MDFlex - A simplistic, modern markdown reader and editor.
Main application module.
Author: Redz
"""

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QToolBar, QFileDialog, QMessageBox, QSplitter,
    QPushButton, QLabel, QComboBox, QToolButton, QMenu, QSizePolicy,
    QStyle, QStyledItemDelegate, QInputDialog
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QTextCharFormat, QTextCursor,
    QKeySequence, QFontDatabase, QPalette, QColor, QTextListFormat,
    QTextBlockFormat, QDesktopServices, QPainter, QPixmap
)
from PyQt6.QtCore import Qt, QSize, QUrl, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtSvg import QSvgRenderer

import markdown
from markdown.extensions import codehilite, fenced_code, tables, toc


def get_icons_dir():
    """Get the path to the icons directory."""
    return Path(__file__).parent / "icons"


class IconButton(QToolButton):
    """Modern icon button for toolbar."""
    def __init__(self, icon=None, tooltip="", parent=None):
        super().__init__(parent)
        if icon:
            self.setIcon(icon)
        self.setToolTip(tooltip)
        self.setFixedSize(32, 32)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class MDFlex(QMainWindow):
    """Main application window for MDFlex."""

    def __init__(self):
        super().__init__()
        self.current_file = None
        self.is_modified = False
        self.is_dark_mode = True  # Start in dark mode
        self.is_edit_mode = True  # Start in edit mode
        self.current_zoom = 100
        self.word_count = 0
        self.char_count = 0
        self.icons_dir = get_icons_dir()
        
        self.init_ui()
        self.apply_theme()
        self.update_mode_display()
        
    def get_icon(self, name):
        """Get icon from custom SVG icons with theme-aware coloring."""
        icon_path = self.icons_dir / f"{name}.svg"
        if icon_path.exists():
            # Read SVG and replace currentColor with theme-appropriate color
            with open(icon_path, 'r') as f:
                svg_content = f.read()
            
            # Use light color for dark mode, dark color for light mode
            icon_color = "#e0e0e0" if self.is_dark_mode else "#333333"
            svg_content = svg_content.replace('currentColor', icon_color)
            svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{icon_color}"')
            svg_content = svg_content.replace('fill="currentColor"', f'fill="{icon_color}"')
            
            # Create pixmap from SVG
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtCore import QByteArray
            
            renderer = QSvgRenderer(QByteArray(svg_content.encode()))
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
        
        # Fallback to theme icons
        if QIcon.hasThemeIcon(name):
            return QIcon.fromTheme(name)
        
        return QIcon()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("MDFlex")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create editor first (needed by toolbar)
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Monospace", 12))
        self.editor.setAcceptRichText(False)
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.setPlaceholderText("Start writing your markdown here...")
        
        # Create preview
        self.preview = QWebEngineView()
        
        # Create toolbar
        self.create_toolbar()
        main_layout.addWidget(self.toolbar_widget)
        
        # Main content - editor OR preview (not both)
        self.content_stack = QWidget()
        self.content_layout = QVBoxLayout(self.content_stack)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addWidget(self.editor)
        self.content_layout.addWidget(self.preview)
        main_layout.addWidget(self.content_stack)
        
        # Create keyboard shortcuts
        self.create_shortcuts()
        
        # Setup auto-preview timer
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_preview)
        
        # Initial preview
        self.update_preview()
        
    def create_toolbar(self):
        """Create the main toolbar with all formatting options."""
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setFixedHeight(44)
        self.toolbar_widget.setObjectName("toolbarWidget")
        
        toolbar_layout = QHBoxLayout(self.toolbar_widget)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(2)
        
        # Menu button
        self.menu_button = IconButton(self.get_icon("menu"), "Menu")
        self.menu_button.clicked.connect(self.show_file_menu)
        toolbar_layout.addWidget(self.menu_button)
        
        # Undo/Redo
        self.undo_btn = IconButton(self.get_icon("undo"), "Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.editor.undo)
        toolbar_layout.addWidget(self.undo_btn)
        
        self.redo_btn = IconButton(self.get_icon("redo"), "Redo (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.editor.redo)
        toolbar_layout.addWidget(self.redo_btn)
        
        # Style dropdown with preview
        self.style_combo = QComboBox()
        self.style_combo.setFixedWidth(95)
        for i, (name, size) in enumerate([
            ("Body", 12), ("H1", 20), ("H2", 18),
            ("H3", 16), ("H4", 14), ("H5", 13), ("H6", 12)
        ]):
            self.style_combo.addItem(name)
            font = QFont()
            font.setPointSize(size)
            if i > 0:
                font.setBold(True)
            self.style_combo.setItemData(i, font, Qt.ItemDataRole.FontRole)
        self.style_combo.currentIndexChanged.connect(self.insert_header)
        toolbar_layout.addWidget(self.style_combo)
        
        # Font family dropdown with preview
        self.font_combo = QComboBox()
        self.font_combo.setFixedWidth(110)
        fonts = ["Default", "Arial", "Times New Roman", "Courier New", "Georgia", "Verdana"]
        for i, font_name in enumerate(fonts):
            self.font_combo.addItem(font_name)
            if font_name != "Default":
                font = QFont(font_name)
                self.font_combo.setItemData(i, font, Qt.ItemDataRole.FontRole)
        toolbar_layout.addWidget(self.font_combo)
        
        # Font size dropdown
        self.size_combo = QComboBox()
        self.size_combo.setFixedWidth(65)
        self.size_combo.addItems(["12px", "14px", "16px", "18px", "20px", "24px", "28px", "32px"])
        self.size_combo.setCurrentText("16px")
        toolbar_layout.addWidget(self.size_combo)
        
        # Text formatting buttons
        self.bold_btn = IconButton(self.get_icon("bold"), "Bold (Ctrl+B)")
        self.bold_btn.clicked.connect(lambda: self.insert_formatting("**", "**"))
        toolbar_layout.addWidget(self.bold_btn)
        
        self.italic_btn = IconButton(self.get_icon("italic"), "Italic (Ctrl+I)")
        self.italic_btn.clicked.connect(lambda: self.insert_formatting("*", "*"))
        toolbar_layout.addWidget(self.italic_btn)
        
        self.underline_btn = IconButton(self.get_icon("underline"), "Underline")
        self.underline_btn.clicked.connect(lambda: self.insert_formatting("<u>", "</u>"))
        toolbar_layout.addWidget(self.underline_btn)
        
        self.strike_btn = IconButton(self.get_icon("strikethrough"), "Strikethrough")
        self.strike_btn.clicked.connect(lambda: self.insert_formatting("~~", "~~"))
        toolbar_layout.addWidget(self.strike_btn)
        
        # Link button
        self.link_btn = IconButton(self.get_icon("link"), "Insert Link")
        self.link_btn.clicked.connect(self.insert_link)
        toolbar_layout.addWidget(self.link_btn)
        
        # Image button
        self.image_btn = IconButton(self.get_icon("image"), "Insert Image")
        self.image_btn.clicked.connect(self.insert_image)
        toolbar_layout.addWidget(self.image_btn)
        
        # Code button
        self.code_btn = IconButton(self.get_icon("code"), "Inline Code")
        self.code_btn.clicked.connect(lambda: self.insert_formatting("`", "`"))
        toolbar_layout.addWidget(self.code_btn)
        
        # Code block button
        self.code_block_btn = IconButton(self.get_icon("code-block"), "Code Block")
        self.code_block_btn.clicked.connect(self.insert_code_block)
        toolbar_layout.addWidget(self.code_block_btn)
        
        # Table button
        self.table_btn = IconButton(self.get_icon("table"), "Insert Table")
        self.table_btn.clicked.connect(self.insert_table)
        toolbar_layout.addWidget(self.table_btn)
        
        # Quote button
        self.quote_btn = IconButton(self.get_icon("quote"), "Blockquote")
        self.quote_btn.clicked.connect(self.insert_quote)
        toolbar_layout.addWidget(self.quote_btn)
        
        # Bullet list button
        self.bullet_btn = IconButton(self.get_icon("list-bullet"), "Bullet List")
        self.bullet_btn.clicked.connect(self.insert_bullet_list)
        toolbar_layout.addWidget(self.bullet_btn)
        
        # Numbered list button
        self.number_btn = IconButton(self.get_icon("list-number"), "Numbered List")
        self.number_btn.clicked.connect(self.insert_numbered_list)
        toolbar_layout.addWidget(self.number_btn)
        
        # Task list button
        self.task_btn = IconButton(self.get_icon("task"), "Task List")
        self.task_btn.clicked.connect(self.insert_task_list)
        toolbar_layout.addWidget(self.task_btn)
        
        # Horizontal rule button
        self.hr_btn = IconButton(self.get_icon("hr"), "Horizontal Rule")
        self.hr_btn.clicked.connect(self.insert_horizontal_rule)
        toolbar_layout.addWidget(self.hr_btn)
        
        # Spacer
        toolbar_layout.addStretch()
        
        # Search button
        self.search_btn = IconButton(self.get_icon("search"), "Search (Ctrl+F)")
        self.search_btn.clicked.connect(self.toggle_search)
        toolbar_layout.addWidget(self.search_btn)
        
        # Theme toggle button
        self.theme_button = IconButton(self.get_icon("moon"), "Toggle Theme (Ctrl+T)")
        self.theme_button.clicked.connect(self.toggle_theme)
        toolbar_layout.addWidget(self.theme_button)
        
        # Mode toggle (Edit/View)
        self.mode_button = IconButton(self.get_icon("edit"), "Edit Mode - Click to switch to View Mode (Ctrl+E)")
        self.mode_button.clicked.connect(self.toggle_mode)
        toolbar_layout.addWidget(self.mode_button)
        
        # Fullscreen button
        self.expand_btn = IconButton(self.get_icon("fullscreen"), "Fullscreen (F11)")
        self.expand_btn.clicked.connect(self.toggle_fullscreen)
        toolbar_layout.addWidget(self.expand_btn)
        
    def show_file_menu(self):
        """Show the file menu from hamburger button."""
        menu = QMenu(self)
        
        new_action = menu.addAction("New")
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_file)
        
        open_action = menu.addAction("Open...")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        
        save_action = menu.addAction("Save")
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        
        save_as_action = menu.addAction("Save As...")
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_file_as)
        
        menu.addSeparator()
        
        export_action = menu.addAction("Export as HTML...")
        export_action.triggered.connect(self.export_html)
        
        menu.addSeparator()
        
        about_action = menu.addAction("About MDFlex")
        about_action.triggered.connect(self.show_about)
        
        help_action = menu.addAction("Markdown Guide")
        help_action.triggered.connect(self.show_markdown_help)
        
        menu.addSeparator()
        
        exit_action = menu.addAction("Exit")
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))
        
    def create_shortcuts(self):
        """Create keyboard shortcuts."""
        # File shortcuts
        new_shortcut = QAction(self)
        new_shortcut.setShortcut(QKeySequence.StandardKey.New)
        new_shortcut.triggered.connect(self.new_file)
        self.addAction(new_shortcut)
        
        open_shortcut = QAction(self)
        open_shortcut.setShortcut(QKeySequence.StandardKey.Open)
        open_shortcut.triggered.connect(self.open_file)
        self.addAction(open_shortcut)
        
        save_shortcut = QAction(self)
        save_shortcut.setShortcut(QKeySequence.StandardKey.Save)
        save_shortcut.triggered.connect(self.save_file)
        self.addAction(save_shortcut)
        
        save_as_shortcut = QAction(self)
        save_as_shortcut.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_shortcut.triggered.connect(self.save_file_as)
        self.addAction(save_as_shortcut)
        
        # Edit shortcuts
        bold_shortcut = QAction(self)
        bold_shortcut.setShortcut(QKeySequence.StandardKey.Bold)
        bold_shortcut.triggered.connect(lambda: self.insert_formatting("**", "**"))
        self.addAction(bold_shortcut)
        
        italic_shortcut = QAction(self)
        italic_shortcut.setShortcut(QKeySequence.StandardKey.Italic)
        italic_shortcut.triggered.connect(lambda: self.insert_formatting("*", "*"))
        self.addAction(italic_shortcut)
        
        find_shortcut = QAction(self)
        find_shortcut.setShortcut(QKeySequence.StandardKey.Find)
        find_shortcut.triggered.connect(self.toggle_search)
        self.addAction(find_shortcut)
        
        # View shortcuts
        toggle_mode_shortcut = QAction(self)
        toggle_mode_shortcut.setShortcut("Ctrl+E")
        toggle_mode_shortcut.triggered.connect(self.toggle_mode)
        self.addAction(toggle_mode_shortcut)
        
        toggle_theme_shortcut = QAction(self)
        toggle_theme_shortcut.setShortcut("Ctrl+T")
        toggle_theme_shortcut.triggered.connect(self.toggle_theme)
        self.addAction(toggle_theme_shortcut)
        
        fullscreen_shortcut = QAction(self)
        fullscreen_shortcut.setShortcut("F11")
        fullscreen_shortcut.triggered.connect(self.toggle_fullscreen)
        self.addAction(fullscreen_shortcut)
        
    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        
    def toggle_theme(self):
        """Toggle between dark and light theme."""
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()
        self.update_preview()
        
    def toggle_mode(self):
        """Toggle between edit and view mode."""
        self.is_edit_mode = not self.is_edit_mode
        self.update_mode_display()
        
    def update_mode_display(self):
        """Update the UI based on current mode."""
        if self.is_edit_mode:
            # Edit mode - show only editor
            self.editor.show()
            self.preview.hide()
            self.mode_button.setIcon(self.get_icon("edit"))
            self.mode_button.setToolTip("Edit Mode - Click to switch to View Mode (Ctrl+E)")
            self.set_edit_tools_visible(True)
        else:
            # View mode - show only preview
            self.update_preview()
            self.editor.hide()
            self.preview.show()
            self.mode_button.setIcon(self.get_icon("eye"))
            self.mode_button.setToolTip("View Mode - Click to switch to Edit Mode (Ctrl+E)")
            self.set_edit_tools_visible(False)
            
    def set_edit_tools_visible(self, visible):
        """Show or hide editing controls."""
        edit_tools = [
            self.undo_btn, self.redo_btn,
            self.style_combo, self.font_combo, self.size_combo,
            self.bold_btn, self.italic_btn, self.underline_btn, self.strike_btn,
            self.link_btn, self.image_btn, self.code_btn, self.code_block_btn,
            self.table_btn, self.quote_btn, self.bullet_btn, self.number_btn,
            self.task_btn, self.hr_btn
        ]
        for tool in edit_tools:
            tool.setVisible(visible)
    
    def toggle_search(self):
        """Toggle search functionality."""
        if self.is_edit_mode:
            text, ok = QInputDialog.getText(self, "Find", "Search for:")
            if ok and text:
                cursor = self.editor.textCursor()
                found = self.editor.find(text)
                if not found:
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    self.editor.setTextCursor(cursor)
                    self.editor.find(text)
        
    def refresh_icons(self):
        """Refresh all toolbar icons with current theme colors."""
        self.menu_button.setIcon(self.get_icon("menu"))
        self.undo_btn.setIcon(self.get_icon("undo"))
        self.redo_btn.setIcon(self.get_icon("redo"))
        self.bold_btn.setIcon(self.get_icon("bold"))
        self.italic_btn.setIcon(self.get_icon("italic"))
        self.underline_btn.setIcon(self.get_icon("underline"))
        self.strike_btn.setIcon(self.get_icon("strikethrough"))
        self.link_btn.setIcon(self.get_icon("link"))
        self.image_btn.setIcon(self.get_icon("image"))
        self.code_btn.setIcon(self.get_icon("code"))
        self.code_block_btn.setIcon(self.get_icon("code-block"))
        self.table_btn.setIcon(self.get_icon("table"))
        self.quote_btn.setIcon(self.get_icon("quote"))
        self.bullet_btn.setIcon(self.get_icon("list-bullet"))
        self.number_btn.setIcon(self.get_icon("list-number"))
        self.task_btn.setIcon(self.get_icon("task"))
        self.hr_btn.setIcon(self.get_icon("hr"))
        self.search_btn.setIcon(self.get_icon("search"))
        self.expand_btn.setIcon(self.get_icon("fullscreen"))
        # Theme and mode icons are set separately based on state
        
    def apply_theme(self):
        """Apply the current theme to the application."""
        if self.is_dark_mode:
            bg_color = "#181818"
            text_color = "#e0e0e0"
            accent_color = "#4a9eff"
            secondary_bg = "#242424"
            border_color = "#333333"
            toolbar_bg = "#1e1e1e"
            button_hover = "#2d2d2d"
            input_bg = "#242424"
        else:
            bg_color = "#ffffff"
            text_color = "#333333"
            accent_color = "#0066cc"
            secondary_bg = "#f5f5f5"
            border_color = "#e0e0e0"
            toolbar_bg = "#fafafa"
            button_hover = "#e8e8e8"
            input_bg = "#ffffff"
        
        # Refresh all icons with new theme colors
        self.refresh_icons()
        self.theme_button.setIcon(self.get_icon("moon" if self.is_dark_mode else "sun"))
        self.mode_button.setIcon(self.get_icon("edit" if self.is_edit_mode else "eye"))
            
        stylesheet = f"""
            QMainWindow {{
                background-color: {bg_color};
            }}
            
            #toolbarWidget {{
                background-color: {toolbar_bg};
                border-bottom: 1px solid {border_color};
            }}
            
            QToolButton {{
                background-color: transparent;
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 4px;
            }}
            QToolButton:hover {{
                background-color: {button_hover};
            }}
            QToolButton:pressed {{
                background-color: {accent_color};
            }}
            QToolButton:disabled {{
                color: #666666;
            }}
            
            QComboBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: {accent_color};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 6px;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {secondary_bg};
                color: {text_color};
                border: 1px solid {border_color};
                selection-background-color: {accent_color};
                selection-color: white;
            }}
            
            QMenu {{
                background-color: {secondary_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {accent_color};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {border_color};
                margin: 4px 8px;
            }}
            
            QTextEdit {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                padding: 20px 30px;
                padding-right: 15px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
                font-size: 14px;
            }}
            
            QScrollBar:vertical {{
                background-color: transparent;
                width: 10px;
                margin: 0;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {border_color};
                border-radius: 5px;
                min-height: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {accent_color};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
                border: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background-color: transparent;
                height: 10px;
                margin: 0;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {border_color};
                border-radius: 5px;
                min-width: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {accent_color};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
                border: none;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            
            /* Dialog styling */
            QDialog {{
                background-color: {secondary_bg};
                color: {text_color};
            }}
            QInputDialog {{
                background-color: {secondary_bg};
                color: {text_color};
            }}
            QInputDialog QLabel {{
                color: {text_color};
            }}
            QInputDialog QLineEdit {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 6px;
            }}
            QMessageBox {{
                background-color: {secondary_bg};
                color: {text_color};
            }}
            QMessageBox QLabel {{
                color: {text_color};
            }}
            QPushButton {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 60px;
            }}
            QPushButton:hover {{
                background-color: {button_hover};
                border-color: {accent_color};
            }}
            QPushButton:pressed {{
                background-color: {accent_color};
                color: white;
            }}
            QPushButton:default {{
                background-color: {accent_color};
                color: white;
                border-color: {accent_color};
            }}
        """
        self.setStyleSheet(stylesheet)
        
    def get_preview_css(self):
        """Get CSS for the preview panel based on current theme."""
        if self.is_dark_mode:
            bg_color = "#181818"
            text_color = "#e0e0e0"
            heading_color = "#ffffff"
            link_color = "#4a9eff"
            code_bg = "#242424"
            pre_bg = "#0d0d0d"
            border_color = "#333333"
            quote_bg = "#242424"
            scrollbar_color = "#333333"
            scrollbar_hover = "#4a9eff"
        else:
            bg_color = "#ffffff"
            text_color = "#333333"
            heading_color = "#1a1a1a"
            link_color = "#0066cc"
            code_bg = "#f5f5f5"
            pre_bg = "#f8f8f8"
            border_color = "#e0e0e0"
            quote_bg = "#f9f9f9"
            scrollbar_color = "#cccccc"
            scrollbar_hover = "#0066cc"
            
        return f"""
            * {{
                scrollbar-width: thin;
                scrollbar-color: {scrollbar_color} {bg_color};
            }}
            ::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}
            ::-webkit-scrollbar-track {{
                background: {bg_color};
            }}
            ::-webkit-scrollbar-thumb {{
                background-color: {scrollbar_color};
                border-radius: 4px;
            }}
            ::-webkit-scrollbar-thumb:hover {{
                background-color: {scrollbar_hover};
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                line-height: 1.7;
                color: {text_color};
                background-color: {bg_color};
                padding: 30px 40px;
                max-width: 900px;
                margin: 0 auto;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: {heading_color};
                margin-top: 1.5em;
                margin-bottom: 0.5em;
                font-weight: 600;
            }}
            h1 {{ font-size: 2.2em; border-bottom: 2px solid {border_color}; padding-bottom: 0.3em; }}
            h2 {{ font-size: 1.8em; border-bottom: 1px solid {border_color}; padding-bottom: 0.3em; }}
            h3 {{ font-size: 1.5em; }}
            h4 {{ font-size: 1.25em; }}
            h5 {{ font-size: 1.1em; }}
            h6 {{ font-size: 1em; color: #888; }}
            p {{ margin: 1em 0; }}
            a {{ color: {link_color}; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            code {{
                font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
                background-color: {code_bg};
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.9em;
            }}
            pre {{
                position: relative;
                background-color: {pre_bg};
                padding: 16px 20px;
                border-radius: 6px;
                overflow-x: auto;
                border: 1px solid {border_color};
            }}
            pre code {{
                background: none;
                padding: 0;
            }}
            .copy-btn {{
                position: absolute;
                top: 8px;
                right: 8px;
                background-color: {code_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                cursor: pointer;
                opacity: 0;
                transition: opacity 0.2s;
            }}
            pre:hover .copy-btn {{
                opacity: 1;
            }}
            .copy-btn:hover {{
                background-color: {link_color};
                color: white;
                border-color: {link_color};
            }}
            .copy-btn.copied {{
                background-color: #28a745;
                border-color: #28a745;
                color: white;
            }}
            blockquote {{
                border-left: 4px solid {link_color};
                margin: 1em 0;
                padding: 0.5em 1em;
                background-color: {quote_bg};
                border-radius: 0 6px 6px 0;
                color: #888;
            }}
            ul, ol {{ padding-left: 2em; margin: 1em 0; }}
            li {{ margin: 0.5em 0; }}
            li.task-list-item {{ list-style-type: none; margin-left: -1.5em; }}
            li.task-list-item input[type="checkbox"] {{
                margin-right: 0.5em;
                accent-color: {link_color};
            }}
            del, s {{ text-decoration: line-through; color: #888; }}
            .table-wrapper {{
                overflow-x: auto;
                margin: 1em 0;
                border-radius: 8px;
                border: 1px solid {border_color};
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 0;
            }}
            th, td {{
                border: 1px solid {border_color};
                padding: 10px 14px;
                text-align: left;
            }}
            th {{
                background-color: {code_bg};
                font-weight: 600;
            }}
            tr:first-child th:first-child {{ border-top-left-radius: 7px; }}
            tr:first-child th:last-child {{ border-top-right-radius: 7px; }}
            tr:last-child td:first-child {{ border-bottom-left-radius: 7px; }}
            tr:last-child td:last-child {{ border-bottom-right-radius: 7px; }}
            tr:nth-child(even) {{ background-color: {quote_bg}; }}
            hr {{ border: none; border-top: 2px solid {border_color}; margin: 2em 0; }}
            img {{ max-width: 100%; height: auto; border-radius: 6px; }}
        """
            
    def on_text_changed(self):
        """Handle text changes in the editor."""
        self.is_modified = True
        self.update_window_title()
        
        text = self.editor.toPlainText()
        self.word_count = len(text.split()) if text.strip() else 0
        self.char_count = len(text)
        
        self.preview_timer.start(300)
        
    def update_preview(self):
        """Update the markdown preview."""
        text = self.editor.toPlainText()
        
        # Process task lists manually (- [ ] and - [x])
        import re
        text = re.sub(r'^(\s*)- \[ \] (.+)$', r'\1<li class="task-list-item"><input type="checkbox" disabled> \2</li>', text, flags=re.MULTILINE)
        text = re.sub(r'^(\s*)- \[x\] (.+)$', r'\1<li class="task-list-item"><input type="checkbox" checked disabled> \2</li>', text, flags=re.MULTILINE)
        text = re.sub(r'^(\s*)- \[X\] (.+)$', r'\1<li class="task-list-item"><input type="checkbox" checked disabled> \2</li>', text, flags=re.MULTILINE)
        
        # Process strikethrough (~~text~~)
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
        
        md = markdown.Markdown(extensions=[
            'fenced_code',
            'codehilite',
            'tables',
            'toc',
            'nl2br',
            'sane_lists',
        ])
        
        html_content = md.convert(text)
        
        # Fix relative image paths if we have a current file
        if self.current_file:
            import os
            base_dir = os.path.dirname(os.path.abspath(self.current_file))
            # Replace relative image paths with absolute file:// URLs
            html_content = re.sub(
                r'<img src="(?!http|file:|data:)([^"]+)"',
                lambda m: f'<img src="file://{os.path.join(base_dir, m.group(1))}"',
                html_content
            )
        
        # Add copy button to code blocks with fallback for QWebEngineView
        copy_script = """
        <script>
        function copyToClipboard(text, btn) {
            // Try modern clipboard API first
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(function() {
                    showCopied(btn);
                }).catch(function() {
                    fallbackCopy(text, btn);
                });
            } else {
                fallbackCopy(text, btn);
            }
        }
        
        function fallbackCopy(text, btn) {
            // Fallback using textarea and execCommand
            var textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            textarea.style.top = '0';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            try {
                document.execCommand('copy');
                showCopied(btn);
            } catch (err) {
                btn.textContent = 'Failed';
                setTimeout(function() {
                    btn.textContent = 'Copy';
                }, 2000);
            }
            document.body.removeChild(textarea);
        }
        
        function showCopied(btn) {
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(function() {
                btn.textContent = 'Copy';
                btn.classList.remove('copied');
            }, 2000);
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('pre').forEach(function(pre) {
                var btn = document.createElement('button');
                btn.className = 'copy-btn';
                btn.textContent = 'Copy';
                btn.onclick = function(e) {
                    e.preventDefault();
                    var code = pre.querySelector('code') || pre;
                    copyToClipboard(code.textContent, btn);
                };
                pre.appendChild(btn);
            });
        });
        </script>
        """
        
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{self.get_preview_css()}</style>
        </head>
        <body>
            {html_content}
            {copy_script}
        </body>
        </html>
        """
        
        self.preview.setHtml(full_html)
        
    def update_window_title(self):
        """Update the window title."""
        if self.current_file:
            name = Path(self.current_file).name
        else:
            name = "Untitled"
            
        if self.is_modified:
            name = f"• {name}"
            
        self.setWindowTitle(f"{name} - MDFlex")
        
    def insert_formatting(self, prefix, suffix):
        """Insert formatting around selected text or at cursor."""
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        
        if selected_text:
            cursor.insertText(f"{prefix}{selected_text}{suffix}")
        else:
            pos = cursor.position()
            cursor.insertText(f"{prefix}{suffix}")
            cursor.setPosition(pos + len(prefix))
            self.editor.setTextCursor(cursor)
            
    def insert_header(self, index):
        """Insert header formatting."""
        if index == 0:
            return
            
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        
        line_text = cursor.selectedText()
        line_text = line_text.lstrip('#').lstrip()
        
        header_prefix = '#' * index + ' '
        cursor.insertText(header_prefix + line_text)
        
        self.style_combo.setCurrentIndex(0)
        
    def insert_bullet_list(self):
        """Insert bullet list item."""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.insertText("- ")
        
    def insert_numbered_list(self):
        """Insert numbered list item."""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.insertText("1. ")
        
    def insert_task_list(self):
        """Insert task list item."""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.insertText("- [ ] ")
        
    def insert_link(self):
        """Insert link template."""
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        
        if selected_text:
            cursor.insertText(f"[{selected_text}](url)")
        else:
            cursor.insertText("[link text](url)")
            
    def insert_image(self):
        """Insert image template."""
        cursor = self.editor.textCursor()
        cursor.insertText("![alt text](image_url)")
        
    def insert_table(self):
        """Insert table template."""
        table = """| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
"""
        cursor = self.editor.textCursor()
        cursor.insertText(table)
        
    def insert_quote(self):
        """Insert blockquote."""
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        
        if selected_text:
            lines = selected_text.split('\u2029')
            quoted = '\n'.join(f"> {line}" for line in lines)
            cursor.insertText(quoted)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.insertText("> ")
            
    def insert_code_block(self):
        """Insert code block."""
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        
        if selected_text:
            cursor.insertText(f"```\n{selected_text}\n```")
        else:
            cursor.insertText("```language\ncode here\n```")
            
    def insert_horizontal_rule(self):
        """Insert horizontal rule."""
        cursor = self.editor.textCursor()
        cursor.insertText("\n---\n")
        
    def new_file(self):
        """Create a new file."""
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Do you want to save changes before creating a new file?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_file():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
                
        self.editor.clear()
        self.current_file = None
        self.is_modified = False
        self.update_window_title()
        self.update_preview()
        
    def open_file(self):
        """Open a markdown file."""
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Do you want to save changes before opening another file?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_file():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
                
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Markdown File", "",
            "Markdown Files (*.md *.markdown *.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.editor.setPlainText(content)
                self.current_file = file_path
                self.is_modified = False
                self.update_window_title()
                self.update_preview()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file:\n{str(e)}")
    
    def load_file(self, file_path, switch_to_read_mode=False):
        """Load a file directly without dialog. Used for command-line arguments."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor.setPlainText(content)
            self.current_file = file_path
            self.is_modified = False
            self.update_window_title()
            self.update_preview()
            
            # Switch to read mode if requested (e.g., when opened from file manager)
            if switch_to_read_mode and self.is_edit_mode:
                self.toggle_mode()
                
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open file:\n{str(e)}")
            return False
                
    def save_file(self):
        """Save the current file."""
        if self.current_file:
            return self._save_to_file(self.current_file)
        else:
            return self.save_file_as()
            
    def save_file_as(self):
        """Save the file with a new name."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Markdown File", "",
            "Markdown Files (*.md);;All Files (*)"
        )
        
        if file_path:
            if not file_path.endswith('.md'):
                file_path += '.md'
            return self._save_to_file(file_path)
        return False
        
    def _save_to_file(self, file_path):
        """Save content to the specified file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.current_file = file_path
            self.is_modified = False
            self.update_window_title()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file:\n{str(e)}")
            return False
            
    def export_html(self):
        """Export the document as HTML."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export as HTML", "",
            "HTML Files (*.html);;All Files (*)"
        )
        
        if file_path:
            if not file_path.endswith('.html'):
                file_path += '.html'
                
            text = self.editor.toPlainText()
            md = markdown.Markdown(extensions=[
                'fenced_code',
                'codehilite',
                'tables',
                'toc',
            ])
            html_content = md.convert(text)
            
            full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{Path(file_path).stem}</title>
    <style>{self.get_preview_css()}</style>
</head>
<body>
    {html_content}
</body>
</html>"""
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(full_html)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not export file:\n{str(e)}")
            
    def show_about(self):
        """Show about dialog with stats."""
        QMessageBox.about(
            self, "About MDFlex",
            f"""<h2>MDFlex</h2>
            <p>Version 1.0.0</p>
            <p>A simplistic, modern markdown reader and editor.</p>
            <p><b>Author:</b> Redz</p>
            <p><b>Email:</b> redzdev@pm.me</p>
            <p><b>GitHub:</b> <a href="https://github.com/NoPeRedz/MDFlex">github.com/NoPeRedz/MDFlex</a></p>
            <hr>
            <p><b>Current Document Stats:</b></p>
            <p>Words: {self.word_count}<br>
            Characters: {self.char_count}</p>
            <hr>
            <p>Built with Python and PyQt6.</p>
            """
        )
        
    def show_markdown_help(self):
        """Show markdown syntax help."""
        help_text = """# Markdown Quick Reference

Welcome to MDFlex! This guide shows all supported markdown features.

---

## Headers

# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6

---

## Text Formatting

**Bold text** using double asterisks
*Italic text* using single asterisks
***Bold and italic*** using triple asterisks
~~Strikethrough~~ using double tildes
<u>Underlined text</u> using HTML tags

---

## Lists

### Unordered List
- First item
- Second item
  - Nested item
  - Another nested item
- Third item

### Ordered List
1. First item
2. Second item
   1. Nested numbered item
   2. Another nested item
3. Third item

### Task List
- [ ] Uncompleted task
- [x] Completed task
- [ ] Another task to do

---

## Links and Images

[Click here for Google](https://google.com)

![Image description](path/to/image.png)

---

## Code

Inline `code` looks like this.

```python
# Code block with syntax highlighting
def hello_world():
    print("Hello, MDFlex!")
    
hello_world()
```

```javascript
// JavaScript example
const greeting = "Hello!";
console.log(greeting);
```

---

## Blockquotes

> This is a blockquote.
> It can span multiple lines.
>
> > Nested blockquotes are also supported.

---

## Tables

| Feature | Status | Notes |
|---------|--------|-------|
| Headers | ✓ | H1-H6 supported |
| Bold | ✓ | **text** |
| Italic | ✓ | *text* |
| Strikethrough | ✓ | ~~text~~ |
| Task Lists | ✓ | - [ ] and - [x] |

---

## Horizontal Rules

Use three dashes, asterisks, or underscores:

---

***

___

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New file |
| Ctrl+O | Open file |
| Ctrl+S | Save file |
| Ctrl+B | Bold |
| Ctrl+I | Italic |
| Ctrl+E | Toggle Edit/View mode |
| Ctrl+T | Toggle Dark/Light theme |
| Ctrl+F | Find |
| F11 | Fullscreen |

---

*Happy writing with MDFlex!* 🚀
"""
        self.editor.setPlainText(help_text)
        if not self.is_edit_mode:
            self.toggle_mode()
        
    def closeEvent(self, event):
        """Handle window close event."""
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Do you want to save changes before closing?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                if self.save_file():
                    event.accept()
                else:
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("MDFlex")
    app.setOrganizationName("Redz")
    
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MDFlex()
    window.show()
    
    # Check for file argument (e.g., when double-clicking a .md file)
    # sys.argv[0] is the script name, sys.argv[1] would be the file path
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            # Load the file and switch to read mode
            window.load_file(file_path, switch_to_read_mode=True)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
