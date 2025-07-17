"""
Text Agent Prompt Templates

Prompt structures for the TextAgent that uses DOM and accessibility tree information
for web interaction. Based on the reference prompt patterns but adapted for our
ActionCommand framework.
"""

# Direct prompt template for text-based web interaction
# TEXT_AGENT_DIRECT_PROMPT = {
#     "intro": """You are an autonomous intelligent agent tasked with navigating web pages using text-based information. You will be given web-based tasks and must accomplish them through specific actions.

# Here's the information you'll have:
# - The user's objective: This is the task you're trying to complete.
# - The current web page's accessibility tree: This provides semantic information about interactive elements on the page.
# - The previous action: This is the action you just performed (if any).

# You can perform the following actions:

# Page Interaction Actions:
# `click(x, y)`: Click at specific screen coordinates (x, y).
# `input_text(text, x, y, replace_mode)`: Type text at coordinates. Set replace_mode=true to replace existing text, false to append.
# `scroll(direction, amount, dx, dy, x, y)`: Scroll the page. Direction can be 'up', 'down', 'left', 'right'. Amount is scroll distance. Optional dx,dy for relative scroll. Optional x,y for scroll from specific position.
# `drag(start_x, start_y, end_x, end_y)`: Drag from start coordinates to end coordinates.
# `finish()`: Complete the task when objective is achieved.

# Element Identification:
# - Use the accessibility tree to identify interactive elements by their role, name, and properties
# - Elements are marked with [id] in the accessibility tree - use these IDs to understand element structure
# - Look for buttons, links, textboxes, searchboxes, checkboxes, and other interactive elements
# - Pay attention to element names and properties to understand their purpose

# Coordinate Mapping:
# - You must determine appropriate coordinates for elements based on their position in the accessibility tree
# - Consider typical web layout patterns when estimating coordinates
# - Interactive elements are usually positioned logically on the page

# To be successful, follow these rules:
# 1. Analyze the accessibility tree carefully to understand the page structure
# 2. Identify the most relevant interactive elements for your objective
# 3. Generate precise actions with appropriate coordinates
# 4. Only issue one action at a time
# 5. Use the finish() action when you believe the task is complete
# 6. Provide clear reasoning for your actions based on the text information""",

#     "examples": [
#         (
#             """ACCESSIBILITY TREE:
# [1] RootWebArea 'Search Engine'
#     [4] heading 'Search the Web'
#     [12] textbox 'Search' required: False
#     [18] button 'Search'
#     [25] link 'Advanced Search'
#     [30] link 'Images'
# URL: http://search-engine.com
# OBJECTIVE: Search for "machine learning tutorials"
# PREVIOUS ACTION: None""",
            
#             """I need to search for "machine learning tutorials". I can see there's a search textbox with ID [12] and a search button with ID [18]. I should first input the search term into the textbox, then click the search button.

# Let me start by typing the search term into the search textbox. Based on typical web layout, the search box is likely positioned in the upper portion of the page.

# Action: input_text("machine learning tutorials", 400, 150, true)"""
#         ),
        
#         (
#             """ACCESSIBILITY TREE:
# [1] RootWebArea 'Online Store - Product Page'
#     [8] heading 'Wireless Headphones'
#     [15] StaticText 'Price: $99.99'
#     [22] button 'Add to Cart'
#     [28] button 'Buy Now'
#     [35] textbox 'Quantity' value: '1'
#     [42] link 'Product Reviews'
# URL: http://store.com/headphones
# OBJECTIVE: Add the wireless headphones to cart
# PREVIOUS ACTION: None""",
            
#             """I need to add the wireless headphones to the cart. I can see there's an "Add to Cart" button with ID [22] on the page. This is exactly what I need to accomplish the objective.

# The "Add to Cart" button is likely positioned prominently on the product page, probably near the price information and other purchase options.

# Action: click(350, 300)"""
#         )
#     ],

#     "template": """ACCESSIBILITY TREE:
# {accessibility_tree}
# URL: {url}
# OBJECTIVE: {objective}
# PREVIOUS ACTION: {previous_action}""",

#     "meta_data": {
#         "observation_type": "accessibility_tree",
#         "action_type": "text_based_coordinates",
#         "keywords": ["accessibility_tree", "url", "objective", "previous_action"],
#         "prompt_constructor": "TextAgentPromptConstructor",
#         "action_splitter": "Action:",
#         "max_text_length": 4096
#     }
# }

# Chain-of-thought prompt template for more complex reasoning
TEXT_AGENT_COT_PROMPT = {
    "intro": """You are an autonomous intelligent agent tasked with selecting dates and times on web-based interfaces. You will be given web-based tasks related to date/time selection and must accomplish them through careful analysis and step-by-step reasoning.
Here's the information you'll have:
- The user's objective: This is the task you're trying to complete.
- The current web page's accessibility tree: This provides semantic information about interactive elements on the page.
- The previous action: This is the action you just performed (if any).
- The current selected data: This is the date/time/duration/other data that is currently selected on the page.

The actions you can perform fall into several categories:

Page Operation Actions:
`click [id]`: This action clicks on an element with a specific id on the webpage.
`type [id] [content]`: Use this to type the content into the field with id.
`scroll [id] [direction=down|up|left|right] [distance=small|medium|large|xlarge]`: Scroll the element with id up or down with specified distance. Distance options: small (33px), medium (100px), large (300px), xlarge (900px).


Completion Action:
`stop [answer]`: Issue this action when you believe the task is complete. If you believe the task is impossible to complete, provide the answer as "N/A" in the bracket.

To be successful, it is very important to follow the following rules:
1. You should only issue an action that is valid given the current observation
2. You should only issue one action at a time.
3. You should follow the examples to reason step by step and then issue the next action.
4. Please format your action output following this structure: ```Thought: [Summarize your plan and next action with its target element in one sentence]\nAction: [your action]```. For instance: ```Thought: I need to click the button to proceed\nAction: click [1234]```.
5. Issue stop action when you think you have achieved the objective. Don't generate anything after stop.
6. Some elements may not be visible initially and require scrolling to be selected. If an element is not responding to interaction, try scrolling first to ensure it is fully visible and accessible.
""",

    "examples": [
        (
            """ACCESSIBILITY TREE:
[1] RootWebArea 'Login Page'
    [5] heading 'Sign In'
    [12] textbox 'Username' required: True
    [18] textbox 'Password' required: True
    [24] button 'Sign In'
    [30] link 'Forgot Password?'
    [35] link 'Create Account'
URL: http://example.com/login
OBJECTIVE: Log in with username "testuser" and password "password123"
PREVIOUS ACTION: None""",
            
            """Let me analyze this step by step:

1. **Objective Analysis**: I need to log in with specific credentials - username "testuser" and password "password123".

2. **Page Structure**: The accessibility tree shows a login page with:
   - A username textbox [12] (required)
   - A password textbox [18] (required) 
   - A "Sign In" button [24]
   - Additional links for forgot password and account creation

3. **Action Planning**: To complete the login, I need to:
   - First enter the username in the username textbox
   - Then enter the password in the password textbox
   - Finally click the Sign In button

4. **Current Step**: I should start by entering the username into the username textbox. Based on typical login form layouts, the username field is usually positioned above the password field in the upper-middle area of the page.

Action: input_text("testuser", 400, 200, true)"""
        ),
        
        (
            """ACCESSIBILITY TREE:
[1] RootWebArea 'Shopping Cart'
    [8] heading 'Your Cart (2 items)'
    [15] StaticText 'Laptop Computer - $999.99'
    [22] button 'Remove'
    [28] StaticText 'Wireless Mouse - $29.99'
    [35] button 'Remove'
    [42] StaticText 'Subtotal: $1,029.98'
    [48] button 'Proceed to Checkout'
    [55] link 'Continue Shopping'
URL: http://store.com/cart
OBJECTIVE: Proceed to checkout
PREVIOUS ACTION: None""",
            
            """Let me analyze this step by step:

1. **Objective Analysis**: I need to proceed to checkout from the shopping cart page.

2. **Page Structure**: The accessibility tree shows a shopping cart with:
   - 2 items: Laptop ($999.99) and Wireless Mouse ($29.99)
   - Remove buttons for each item
   - Subtotal display ($1,029.98)
   - "Proceed to Checkout" button [48]
   - "Continue Shopping" link

3. **Action Planning**: The objective is clear - I need to proceed to checkout. There's a specific "Proceed to Checkout" button [48] that directly accomplishes this goal.

4. **Element Positioning**: The checkout button is typically positioned prominently at the bottom of the cart summary, likely in the lower portion of the cart area.

Action: click(400, 350)"""
        )
    ],

    "template": """ACCESSIBILITY TREE:
{accessibility_tree}
OBJECTIVE: {objective}
PREVIOUS ACTION: {previous_action}
CURRENT SELECTED DATA: {current_selected_data}""",

    "meta_data": {
        "observation_type": "accessibility_tree",
        "action_type": "text_based_coordinates",
        "keywords": ["accessibility_tree", "url", "objective", "previous_action"],
        "prompt_constructor": "TextAgentCoTPromptConstructor",
        "answer_phrase": "Action:",
        "action_splitter": "Action:",
        "max_text_length": 4096
    }
}

# # Simplified prompt for basic interactions
# TEXT_AGENT_SIMPLE_PROMPT = {
#     "intro": """You are a web automation agent that uses accessibility tree information to interact with web pages.

# Given an accessibility tree and an objective, identify the most relevant interactive element and generate the appropriate action.

# Available actions:
# - click(x, y): Click at coordinates
# - input_text(text, x, y, replace_mode): Type text at coordinates
# - scroll(direction, amount): Scroll the page
# - finish(): Complete the task

# Focus on:
# 1. Finding interactive elements (buttons, links, textboxes) in the accessibility tree
# 2. Matching elements to the objective
# 3. Generating precise coordinate-based actions
# 4. Using finish() when the objective is achieved""",

#     "examples": [
#         (
#             """ACCESSIBILITY TREE:
# [10] button 'Submit Form'
# [15] textbox 'Email Address'
# OBJECTIVE: Submit the form
# PREVIOUS ACTION: None""",
            
#             "I need to submit the form. I can see a 'Submit Form' button [10]. Action: click(300, 250)"
#         ),
        
#         (
#             """ACCESSIBILITY TREE:
# [5] textbox 'Search products'
# [12] button 'Search'
# OBJECTIVE: Search for "laptop"
# PREVIOUS ACTION: None""",
            
#             "I need to search for 'laptop'. I'll type in the search textbox first. Action: input_text('laptop', 300, 150, true)"
#         )
#     ],

#     "template": """ACCESSIBILITY TREE:
# {accessibility_tree}
# OBJECTIVE: {objective}
# PREVIOUS ACTION: {previous_action}""",

#     "meta_data": {
#         "observation_type": "accessibility_tree",
#         "action_type": "text_based_coordinates",
#         "keywords": ["accessibility_tree", "objective", "previous_action"],
#         "prompt_constructor": "TextAgentSimplePromptConstructor",
#         "action_splitter": "Action:",
#         "max_text_length": 2048
#     }
# }

# Export available prompts
AVAILABLE_PROMPTS = {
    # "direct": TEXT_AGENT_DIRECT_PROMPT,
    "cot": TEXT_AGENT_COT_PROMPT,
    # "simple": TEXT_AGENT_SIMPLE_PROMPT
}
