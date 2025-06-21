import io
import math
import requests
import base64
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from io import BytesIO
from PIL import Image


class PicState:
    def __init__(self, background_path, state):
        """
        background_path: Path to the background image.
        state: [ { id, coord, name, url, freepik_id }, ... ]
                each inner dictionary represents an icon with its properties.
        """
        self.background_path = background_path
        self.state = state

        # self.state: [ { id, coord, name, url, freepik_id, img }, ... ]
        for entry in self.state: 
            response = requests.get(entry['url'])
            response.raise_for_status()
            # a PIL.Image.Image object
            # use case: ax.imshow(img)
            entry['img'] = Image.open(BytesIO(response.content)) 

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
            x, y = entry['coord']
            w, h = entry['img'].size
            ax.imshow(entry['img'], extent=(x - w // 2, x + w // 2, y + h // 2, y - h // 2))
    
        # plt.gca().invert_yaxis()
        plt.tight_layout()  
        # return fig, ax            

    def _draw_mappings(self, ax, thumbnail_size=(50, 50), columns=3):
        
        rows = -(-len(self.state) // columns)  # Ceiling division

        # Create subplots for mappings
        for i in range(rows):
            for j in range(columns):
                if i * columns + j < len(self.state):
                    # Create a new inset axis
                    # inset_ax = ax.inset_axes([j/columns, 1 - (i+1)/rows, 1/columns, 1/rows])
                    inset_ax = ax.inset_axes([j / columns, 1 - (i + 1) / rows, 1 / columns, 1 / rows * 0.85]) 
                    obj = self.state[i * columns + j]

                    img = obj['img'].resize(thumbnail_size)
                    
                    inset_ax.imshow(img)
                    inset_ax.set_title(f"ID: {obj['id']}", fontsize=10)
                    inset_ax.axis('off')

        plt.tight_layout()

    def draw(self, filename=None):       
        """
        Return the base64 encoded image for LLM,
        """ 
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

    def update(self, icon_id, X, Y):
        """
        When model plays `move(ID, X, Y)`, 
        update the state.
        """
        # Update the coordinates for the object with the specified ID
        for obj in self.state:
            if obj['id'] == icon_id:
                # Assuming `coord` is a tuple of (x, y)
                obj['coord'] = (X, Y)  # overwrite coordinates
                break  # Exit loop once the object is found

    def update_and_draw(self, icon_id, X, Y): 
        self.update(icon_id, X, Y)
        return self.draw()

    def get_element_by_id(self, icon_id):
        """
        Returns the element with the specified ID.
        """
        for obj in self.state:
            if obj['id'] == icon_id:
                return obj
        return None

    def _compute_euclidean_distance(self, coord1, coord2):
        """
        Computes the Euclidean distance between two coordinates.
        """
        x1, y1 = coord1
        x2, y2 = coord2
        return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
    
    def get_pairwise_distance(self, other, toRound=False): 
        """
        Compares two PicState instances and returns a dictionary of pairwise distances
        between the identical objects (icons with the same freepik_id).

        Returns:
            distances: { freepik_id: distance, ... }
            where distance is the Euclidean distance between the coordinates of the objects.
        """
        if not isinstance(other, PicState):
            raise ValueError("Comparison is only supported between two PicState instances")
        
        distances = {}
        for obj in self.state:
            # freepik_id is the real unique identifier 
            target_freepik_id = obj['freepik_id']
            for other_obj in other.state:
                if other_obj['freepik_id'] == target_freepik_id:
                    dist = self._compute_euclidean_distance(obj['coord'], other_obj['coord'])
                    if toRound: # for display as log in transcript
                        dist = round(dist, 2)  
                    distances[obj['freepik_id']] = dist
        return dict(sorted(distances.items()))

    
    def distance_sum(self, other):
        """
        Compares two PicState instances and returns the sum of Euclidean distances
        between the identical objects.
        """
        if not isinstance(other, PicState):
            raise ValueError("Comparison is only supported between two PicState instances")
        distances = self.get_pairwise_distance(other)
        if not distances:
            return 0.0
        return sum(distances.values())
    
    def distance_score(self, other):
        """
        Returns a score based on the distance sum compared to the worst case scenario.
        """
        if not isinstance(other, PicState):
            raise ValueError("Comparison is only supported between two PicState instances")
        
        distance_sum = self.distance_sum(other)
        expected_distance_sum = self.expected_total_distance()
        min_max_normed = distance_sum / expected_distance_sum
        return max(1 - min_max_normed, 0)
        return (1 - min_max_normed) ** 4
    

    def expected_total_distance(self):
        """
        Returns the expected total distance for a given number of objects, 
        when they are randomly scattered on a background picture.
        """
        avg_x_dist = (self.bg_width ** 2 - 1) / (3 * self.bg_width)
        avg_y_dist = (self.bg_height ** 2 - 1) / (3 * self.bg_height)
        avg_dist = (avg_x_dist ** 2 + avg_y_dist ** 2) ** 0.5
        return avg_dist * len(self.state)