from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from printer_models import TaskPrintRequest, Priority, TaskCategory
import os

class ImageCardDesigner:
    def __init__(self, width=384, font_path="zpix.ttf"):
        self.width = width
        self.font_path = font_path
        self.margin = 15
        self.content_width = width - (2 * self.margin)
        
        # Load fonts with increased sizes for better readability
        try:
            self.title_font = ImageFont.truetype(font_path, 24)  # Increased from 20
            self.body_font = ImageFont.truetype(font_path, 18)   # Increased from 16
            self.small_font = ImageFont.truetype(font_path, 16)  # Increased from 14
            self.tiny_font = ImageFont.truetype(font_path, 14)   # Increased from 12
        except:
            # Fallback to default font
            self.title_font = ImageFont.load_default()
            self.body_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
            self.tiny_font = ImageFont.load_default()
    
    def create_task_card(self, task: TaskPrintRequest) -> Image.Image:
        # Calculate height based on content
        height = self._calculate_card_height(task)
        
        # Create white background
        img = Image.new('RGB', (self.width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        y_offset = 0
        
        # Draw tear-off perforation at top
        y_offset = self._draw_tear_line(draw, y_offset)
        y_offset += 15
        
        # Draw priority badge
        y_offset = self._draw_priority_badge(draw, task.priority, y_offset)
        y_offset += 10
        
        # Draw category if present
        if task.category:
            y_offset = self._draw_category(draw, task.category, y_offset)
            y_offset += 10
        
        # Draw title
        y_offset = self._draw_title(draw, task.title, y_offset)
        y_offset += 15
        
        # Draw description if present
        if task.description:
            y_offset = self._draw_description(draw, task.description, y_offset)
            y_offset += 15
        
        # Draw metadata (due date, time only)
        y_offset = self._draw_metadata(draw, task, y_offset)
        y_offset += 10
        
        # Draw tear-off perforation at bottom
        self._draw_tear_line(draw, y_offset)
        
        return img
    
    def _calculate_card_height(self, task: TaskPrintRequest) -> int:
        height = 40  # Top tear + margin
        height += 35  # Priority badge
        
        if task.category:
            height += 25  # Category
        
        # Title height (estimate based on wrapping) - increased for larger font
        title_lines = len(self._wrap_text(task.title, self.title_font, self.content_width))
        height += title_lines * 30 + 15
        
        # Description height - increased for larger font
        if task.description:
            desc_lines = len(self._wrap_text(task.description, self.body_font, self.content_width))
            height += desc_lines * 22 + 15
        
        # Metadata (simplified)
        height += 30
        
        height += 25  # Bottom tear + margin
        
        return height
    
    def _draw_tear_line(self, draw: ImageDraw, y: int) -> int:
        # Draw dotted perforation line
        for x in range(0, self.width, 8):
            draw.line([(x, y), (x + 4, y)], fill='black', width=1)
        
        # Add scissors icons at edges
        draw.text((5, y - 8), "✂", font=self.tiny_font, fill='black')
        draw.text((self.width - 20, y - 8), "✂", font=self.tiny_font, fill='black')
        
        return y + 10
    
    def _draw_priority_badge(self, draw: ImageDraw, priority: Priority, y: int) -> int:
        badge_height = 25
        
        # Different styles for different priorities
        if priority == Priority.HIGH:
            # Solid black background for high priority
            draw.rectangle([(self.margin, y), (self.width - self.margin, y + badge_height)], 
                          fill='black')
            text_color = 'white'
            text = "🚨 HIGH PRIORITY"
        elif priority == Priority.MEDIUM:
            # Gray border for medium priority
            draw.rectangle([(self.margin, y), (self.width - self.margin, y + badge_height)], 
                          outline='black', width=2, fill='white')
            text_color = 'black'
            text = "⚠️ MEDIUM PRIORITY"
        else:
            # Dotted border for low priority
            for x in range(self.margin, self.width - self.margin, 8):
                draw.line([(x, y), (x + 4, y)], fill='black', width=1)
                draw.line([(x, y + badge_height), (x + 4, y + badge_height)], fill='black', width=1)
            for y_dot in range(y, y + badge_height, 8):
                draw.line([(self.margin, y_dot), (self.margin, y_dot + 4)], fill='black', width=1)
                draw.line([(self.width - self.margin, y_dot), (self.width - self.margin, y_dot + 4)], fill='black', width=1)
            text_color = 'black'
            text = "✅ LOW PRIORITY"
        
        # Center the text
        bbox = draw.textbbox((0, 0), text, font=self.small_font)
        text_width = bbox[2] - bbox[0]
        text_x = (self.width - text_width) // 2
        draw.text((text_x, y + 5), text, font=self.small_font, fill=text_color)
        
        return y + badge_height
    
    def _draw_category(self, draw: ImageDraw, category: TaskCategory, y: int) -> int:
        category_icons = {
            TaskCategory.WORK: "💼 WORK",
            TaskCategory.PERSONAL: "👤 PERSONAL",
            TaskCategory.URGENT: "🚨 URGENT",
            TaskCategory.LEARNING: "📚 LEARNING",
            TaskCategory.HEALTH: "❤️ HEALTH",
            TaskCategory.OTHER: "📌 OTHER"
        }
        
        text = category_icons.get(category, f"📁 {category.value.upper()}")
        
        # Draw with light gray background
        bbox = draw.textbbox((0, 0), text, font=self.tiny_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Background rectangle
        padding = 5
        draw.rectangle([
            (self.margin, y), 
            (self.margin + text_width + padding * 2, y + text_height + padding * 2)
        ], fill='lightgray', outline='gray')
        
        draw.text((self.margin + padding, y + padding), text, font=self.tiny_font, fill='black')
        
        return y + text_height + padding * 2
    
    def _draw_title(self, draw: ImageDraw, title: str, y: int) -> int:
        lines = self._wrap_text(title, self.title_font, self.content_width)
        
        for line in lines:
            draw.text((self.margin, y), line, font=self.title_font, fill='black')
            y += 30  # Increased spacing for larger font
        
        return y
    
    def _draw_description(self, draw: ImageDraw, description: str, y: int) -> int:
        # Draw separator line
        draw.line([(self.margin, y), (self.width - self.margin, y)], fill='gray', width=1)
        y += 10
        
        # Truncate description if too long
        desc = description[:120] + "..." if len(description) > 120 else description
        lines = self._wrap_text(desc, self.body_font, self.content_width)
        
        for line in lines:
            draw.text((self.margin, y), line, font=self.body_font, fill='black')
            y += 22  # Increased spacing for larger font
        
        return y
    
    def _draw_metadata(self, draw: ImageDraw, task: TaskPrintRequest, y: int) -> int:
        # Only show metadata if there's something to show
        metadata_items = []
        
        if task.due_date:
            metadata_items.append(f"📅 Due: {task.due_date.strftime('%b %d, %Y')}")
        
        if task.estimated_time:
            metadata_items.append(f"⏱️ Time: {task.estimated_time}")
        
        if metadata_items:
            # Draw separator line only if we have metadata
            draw.line([(self.margin, y), (self.width - self.margin, y)], fill='gray', width=1)
            y += 12
            
            for item in metadata_items:
                draw.text((self.margin, y), item, font=self.small_font, fill='black')
                y += 20  # Increased spacing for larger font
        
        return y
    
    
    def _wrap_text(self, text: str, font: ImageFont, max_width: int) -> list:
        """Wrap text to fit within max_width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Word is too long, force break
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines