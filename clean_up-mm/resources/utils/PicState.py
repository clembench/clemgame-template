import io
import base64

from PIL import Image
import matplotlib.image as mpimg
import matplotlib.pyplot as plt


class PicState:
    def __init__(self, background_path, state):
        self.background_path = background_path
        self.state = state

        # Load background image and get dimensions
        self.bg_img = Image.open(self.background_path)
        self.bg_width, self.bg_height = self.bg_img.size

    def _draw_overlay(self, ax):
        # Load background image
        bg_img = mpimg.imread(self.background_path)
        ax.imshow(bg_img)
        ax.set_xticks(range(0, bg_img.shape[1], 50))
        ax.set_yticks(range(0, bg_img.shape[0], 50))
        plt.xticks(rotation=45)  # why this line not working
        # ax.grid(True, color='white', linestyle='--', linewidth=0.5)

        # Fix view limits BEFORE adding overlay
        ax.set_xlim(0, bg_img.shape[1])
        ax.set_ylim(bg_img.shape[0], 0)  # y-axis top-down

        # Overlay each image in state
        for entry in self.state:
            overlay_img = Image.open(entry['icon_path'])
            x, y = entry['coord']
            w, h = overlay_img.size
            ax.imshow(overlay_img, extent=(x - w // 2, x + w // 2, y + h // 2, y - h // 2))
    
        # plt.gca().invert_yaxis()
        plt.tight_layout()
        # return fig, ax            

    def _draw_mappings(self, ax, thumbnail_size=(50, 50), columns=3):
        # state is of format [{id, path, coord}], each inner dictionary represents an image
        rows = -(-len(self.state) // columns)  # Ceiling division

        # Create subplots for mappings
        for i in range(rows):
            for j in range(columns):
                if i * columns + j < len(self.state):
                    # Create a new inset axis
                    # inset_ax = ax.inset_axes([j/columns, 1 - (i+1)/rows, 1/columns, 1/rows])
                    inset_ax = ax.inset_axes([j / columns, 1 - (i + 1) / rows, 1 / columns, 1 / rows * 0.85]) 
                    obj = self.state[i * columns + j]

                    img = Image.open(obj["icon_path"]).resize(thumbnail_size)
                    
                    inset_ax.imshow(img)
                    inset_ax.set_title(f"ID: {obj['id']}", fontsize=10)
                    inset_ax.axis('off')

        plt.tight_layout()

    # return the base64 encoding for LLM,
    def draw(self, filename=None):        

        # Create a gridspec with different proportions for the two subplots
        fig = plt.figure(figsize=(14, 6))
        gs = fig.add_gridspec(1, 2, width_ratios=[2, 1])  # 2:1 ratio
        
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1])  
        ax2.set_xticks([])  
        ax2.set_yticks([])  
    
        self._draw_overlay(ax1)
        self._draw_mappings(ax2)
    
        plt.tight_layout()

        # plt.savefig(filename, bbox_inches='tight', dpi=100)  
        # plt.show()

        # Save to buffer instead of file
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close(fig)  # Close the figure to free memory

        # Encode buffer to base64
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()

        return image_base64        

    """
    When model plays `move(ID, X, Y)`, 
    update the state.
    """
    def update(self, icon_id, X, Y):
        # Update the coordinates for the object with the specified ID
        for obj in self.state:
            if obj['id'] == icon_id:
                # Assuming `coord` is a tuple of (x, y)
                obj['coord'] = (X, Y)  # overwrite coordinates
                break  # Exit loop once the object is found

    def update_and_draw(self, icon_id, X, Y): 
        self.update(icon_id, X, Y)
        return self.draw()
    
    def distance_sum(self, other):
        """
        Compares two PicState instances and returns the sum of Euclidean distances
        between the identical objects.
        """
        if not isinstance(other, PicState):
            raise ValueError("Comparison is only supported between two PicState instances")
        
        total_distance = 0.0
        for obj in self.state:
            for other_obj in other.state:
                # for now, icon_path is the real unique identifier 
                if obj['icon_path'] == other_obj['icon_path']:
                    x1, y1 = obj['coord']
                    x2, y2 = other_obj['coord']
                    distance = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
                    total_distance += distance
        return total_distance
    
    def worst_distance_sum(self):
        """
        Worst case scenario: all identical objects are at opposite corners of the grid.
        """
        max_distance = ((self.bg_width - 1) ** 2 + (self.bg_height - 1) ** 2) ** 0.5
        return max_distance * len(self.state)
    
    def distance_score(self, other):
        """
        Returns a score based on the distance sum compared to the worst case scenario.
        """
        if not isinstance(other, PicState):
            raise ValueError("Comparison is only supported between two PicState instances")
        
        distance_sum = self.distance_sum(other)
        worst_case = self.worst_distance_sum()
        return 1 - (distance_sum / worst_case)
    