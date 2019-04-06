import math

import cv2 as cv
from imutils import contours as cutils
import numpy as np

import utils

class TestBox:

    def __init__(self, page, config, verbose_mode, debug_mode):
        '''
        Constructor for a new test box.

        Args:
            page (numpy.ndarray): An ndarray representing the test image.
            config (dict): A dictionary containing the config file values for 
                this test box.
            verbose_mode (bool): True to run program in verbose mode, False 
                otherwise.
            debug_mode (bool): True to run the program in debug mode, False 
                otherwise.

        Returns:
            TestBox: A newly created test box.

        '''
        # Args.
        self.page = page
        self.config = config
        self.verbose_mode = verbose_mode
        self.debug_mode = debug_mode

        # Configuration values.
        self.name = config['name']
        self.type = config['type']
        self.orientation = config['orientation']
        self.x = config['x']
        self.y = config['y']
        self.rows = config['rows']
        self.columns = config['columns']
        self.groups = config['groups']
        self.bubble_width = config['bubble_width']
        self.bubble_height = config['bubble_height']
        self.x_error = config['x_error']
        self.y_error = config['y_error']

        # Set number of bubbles per question based on box orientation.
        if (self.orientation == 'left-to-right'):
            self.bubbles_per_q = self.columns
        elif (self.orientation == 'top-to-bottom'):
            self.bubbles_per_q = self.rows

        # Return values.
        self.bubbled = []
        self.unsure = []
        self.images = []
        self.status = 0
        self.error = ''

    def is_bubble(self, contour, bubbles):
        '''
        Checks if a contour is of sufficient width and height, is somewhat
        circular, and is within the correct coordinates, with margins for error,
        to be counted as a bubble.

        Args:
            contour (numpy.ndarray): An ndarray representing the contour being 
                checked.
            bubbles (list): A list of lists, where each list is a group of
                bubble contours.

        '''
        (x, y, w, h) = cv.boundingRect(contour)
        aspect_ratio = w / float(h)

        # Add offsets to get coordinates in relation to the whole test image 
        # instead of in relation to the test box.
        x += self.x
        y += self.y

        # Ignore contour if not of sufficient width or height, or not circular.
        if (w < self.bubble_width * 0.9 or 
            h < self.bubble_height * 0.9 or
            aspect_ratio < 0.7 or
            aspect_ratio > 1.3):
            return

        # If the contour fits the coordinates of a bubble group, add it to that
        # group.
        for (i, group) in enumerate(self.groups):
            if (x >= group['x_min'] - self.x_error and
                x <= group['x_max'] + self.x_error and
                y >= group['y_min'] - self.y_error and
                y <= group['y_max'] + self.y_error):
                bubbles[i].append(contour)
                break

    def get_bubbles(self, box):
        '''
        Finds and return bubbles within the test box.

        Args:
            box (numpy.ndarray): An ndarray representing a test box.

        Returns:
            bubbles (list): A list of lists, where each list is a group of 
                bubble contours.

        '''
        # Find bubbles in box.
        _, contours, _ = cv.findContours(box, cv.RETR_EXTERNAL, 
            cv.CHAIN_APPROX_SIMPLE)

        # Init empty list for each group of bubbles.
        bubbles = []
        for _ in range(len(self.groups)):
            bubbles.append([])

        # Check if contour is bubble; if it is, add to its appropriate group.
        for contour in contours:
            self.is_bubble(contour, bubbles)

        return bubbles

    def is_box(self, contour):
        '''
        Checks if x and y coordinates of a contour match the x and y coordinates
        of this test box, with margins for error.

        Args:
            contour (numpy.ndarray): An ndarray representing the contour being 
                checked.

        Returns:
            bool: True for success, False otherwise.

        '''
        (x, y, _, _) = cv.boundingRect(contour)

        if ((self.x - self.x_error <= x <= self.x + self.x_error) and 
            (self.y - self.y_error <= y <= self.y + self.y_error)):
            return True
        else:
            return False

    def get_box_helper(self, im):
        '''
        Finds and returns the box with bubbles as external contours, not a box
        within a box.

        Args:
            im (numpy.ndarray): An ndarray representing the possible test box.

        Returns:
            box (numpy.ndarray): An ndarray representing the test box.

        '''
        # Find external contours of the test box.
        _, contours, _ = cv.findContours(im, cv.RETR_EXTERNAL, 
            cv.CHAIN_APPROX_SIMPLE)
        box = im

        # A box within a box will have 1 external contour; continue looping
        # until multiple external contours are found.
        while (len(contours) == 1):
            box = utils.get_transform(contours[0], im)
            _, contours, _ = cv.findContours(box, cv.RETR_EXTERNAL, 
                cv.CHAIN_APPROX_SIMPLE)

        return box

    def get_box(self):
        '''
        Finds and returns the contour for this test answer box.

        Returns:
            numpy.ndarray: An ndarray representing the answer box in
                the test image.

        '''
        # Blur and threshold the page, then find boxes within the page.
        threshold = utils.get_threshold(self.page)
        _, contours, _ = cv.findContours(threshold, cv.RETR_TREE, 
            cv.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv.contourArea, reverse=True)

        # Iterate through contours until the correct box is found.
        for contour in contours:
            if (self.is_box(contour)):
                box = utils.get_transform(contour, threshold)

                # Find inner contours to verify that the box contains bubbles.
                _, inner_contours, _ = cv.findContours(box, cv.RETR_TREE, 
                    cv.CHAIN_APPROX_SIMPLE)

                if (len(inner_contours) > 4):
                    return self.get_box_helper(box)

        return None

    def init_questions(self):
        '''
        Initialize and return a list of empty lists based on the number of
        questions in a group.

        Returns:
            questions (list): A list of empty lists.

        '''
        questions = []

        if (self.orientation == 'left-to-right'):
            num_questions = self.rows
        elif (self.orientation == 'top-to-bottom'):
            num_questions = self.columns

        for _ in range(num_questions):
            questions.append([])

        return questions

    def get_question_diff(self, config):
        '''
        Finds and returns the distance between each question.

        Args:
            config (dict): A dict containing the config values for this bubble
                group.

        Returns:
            float: The distance between questions in this bubble group.

        '''
        if (self.orientation == 'left-to-right'):
            if (self.rows == 1):
                return 0
            else:
                return (config['y_max'] - config['y_min']) / (self.rows - 1)
        elif (self.orientation == 'top-to-bottom'):
            if (self.columns == 1):
                return 0
            else:
                return (config['x_max'] - config['x_min']) / (self.columns - 1)

    def get_question_offset(self, config):
        '''
        Returns the starting point for this group of bubbles.

        Args:
            config (dict): A dict containing the config values for this bubble
                group.

            Returns:
                float: The starting point for this group of bubbles.

        '''
        if (self.orientation == 'left-to-right'):
            return config['y_min'] - self.y
        elif (self.orientation == 'top-to-bottom'):
            return config['x_min'] - self.x

    def get_question_num(self, bubble, diff, offset):
        '''
        Finds and returns the question number of a bubble based on its 
        coordinates.

        Args:
            bubble (numpy.ndarray): An ndarray representing a bubble contour.
            diff (float): The distance between questions in this bubble group.
            offset (float): The starting point for this group of bubbles.

        Returns:
            int: The question number of this bubble.

        '''
        if (diff == 0):
            return 0

        (x, y, _, _) = cv.boundingRect(bubble)

        if (self.orientation == 'left-to-right'):
            return round((y - offset) / diff)
        elif (self.orientation == 'top-to-bottom'):
            return round((x - offset) / diff)     

    def group_by_question(self, bubbles, config):
        '''
        Groups a list of bubbles by question.

        Args:
            bubbles (list): A list of bubble contours.

        Returns:
            questions (list): A list of lists, where each list contains the 
                bubble contours for a question.

        '''
        questions = self.init_questions()
        diff = self.get_question_diff(config)
        offset = self.get_question_offset(config)
        num_questions = len(questions)

        for bubble in bubbles:
            question_num = self.get_question_num(bubble, diff, offset)
            questions[question_num].append(bubble)

        return questions

    def handle_unsure_question(self, question_num, box):
        '''
        Adds the question to the list of unsure questions. Adds the image slice
        for the question to the list of images.

        Args:
            question_num (int): The question number.
            box (numpy.ndarray): An ndarray representing the test box image.

        '''
        # TODO get image slice for unsure question.
        self.unsure.append(question_num)

    def get_percent_marked(self, bubble, box):
        '''
        Calculates the percentage of darkened pixels in the bubble contour.

        Args:
            bubble (numpy.ndarray): An ndarray representing the bubble.
            box (numpy.ndarray): An ndarray representing the test box image.

        Returns:
            float: The percentage of darkened pixels in the bubble contour.

        '''
        # Applies a mask to the entire test box image to only look at one
        # bubble, then counts the number of nonzero pixels in the bubble.
        mask = np.zeros(box.shape, dtype="uint8")
        cv.drawContours(mask, [bubble], -1, 255, -1)
        mask = cv.bitwise_and(box, box, mask=mask)
        total = cv.countNonZero(mask)
        (x, y, w, h) = cv.boundingRect(bubble)
        area = math.pi * ((min(w, h) / 2) ** 2)

        return (total / area)

    def format_answer(self, bubbled):
        '''
        Formats the answer for this question (string of letters or numbers).

        Args:
            bubbled (str): A string representing the graded answer.

        Returns:
            str: A formatted string representing the graded answer, or '-' for
                an unmarked answer.

        '''
        if (bubbled == ''):
            return '-'
        if (self.type == 'number'):
            return bubbled
        elif (self.type == 'letter'):
            return ''.join([chr(int(c) + 65) for c in bubbled])

    def grade_question(self, question, question_num, box):
        '''
        Grades a question and adds the result to the 'bubbled' list.

        Args:
            question (list): A list of bubble contours for the question being
                graded.
            question_num (int): The question number.
            box (numpy.ndarray): An ndarray representing the test box image.

        '''
        bubbled = ''

        # If question is missing bubbles, mark as unsure.
        if (len(question) != self.bubbles_per_q):
            self.handle_unsure_question(question_num, box)
            self.bubbled.append('?')
            return

        for (i, bubble) in enumerate(question):
                percent_marked = self.get_percent_marked(bubble, box)

                # If ~50% bubbled, count as marked.
                if (percent_marked > 0.8):
                    bubbled += str(i)
                # Count as unsure.
                elif (percent_marked > 0.75):
                    self.handle_unsure_question(question_num, box)
                    self.bubbled.append('?')
                    break

        self.bubbled.append(self.format_answer(bubbled))

    def grade_bubbles(self, bubbles, box):
        '''
        Grades a list of bubbles from the test box.

        Args:
            bubbles (list): A list of lists, where each list is a group of 
                bubble contours.
            box (numpy.ndarray): An ndarray representing the test box.

        '''
        for (i, group) in enumerate(bubbles):
            # Split a group of bubbles by question.
            group = self.group_by_question(group, self.groups[i])

            # Sort bubbles in each question based on box orientation then grade.
            for (j, question) in enumerate(group, 1):
                question_num = j + (i * len(group))
                question, _ = cutils.sort_contours(question,
                    method=self.orientation)

                self.grade_question(question, question_num, box)

    def grade(self):
        '''
        Finds and grades a test box within a test image.

        Returns:
            data (dict): A dictionary containing info about the graded test box.

        '''
        # Initialize dictionary to be returned.
        data = {
            'status' : 0,
            'error' : ''
        }

        # Find box, find bubbles in box, then grade bubbles.
        box = self.get_box()
        bubbles = self.get_bubbles(box)
        self.grade_bubbles(bubbles, box)

        # Add results of grading to return value.
        data['bubbled'] = self.bubbled
        data['unsure'] = self.unsure
        data['images'] = self.images
        data['status'] = self.status
        data['error'] = self.error

        return data

