"""Functions to manage a users shopping cart items."""


def add_item(current_cart, items_to_add):
    """Add items to shopping cart.

    Parameters:
        current_cart (dict): The current shopping cart.
        items_to_add (iterable): The items to add to the cart.

    Returns:
        dict: The updated user cart dictionary.
    """
    
    for keys in items_to_add:
        if keys in current_cart.keys():
            current_cart[keys] += 1
        else:
            current_cart[keys] = 1
    return current_cart
    
            
            


def read_notes(notes):
    """Create user cart from an iterable notes entry.

    Parameters:
        notes (iterable): Group of items to add to cart.

    Returns:
        dict: A user shopping cart dictionary.
    """

    shoppingCart = dict.fromkeys(notes,1 )
    return shoppingCart
    
        


def update_recipes(ideas, recipe_updates):
    """Update the recipe ideas dictionary.

    Parameters:
        ideas (dict): The "recipe ideas" dict.
        recipe_updates (iterable): Updates for the ideas section.

    Returns:
        dict: The updated "recipe ideas" dict.
    """
    ideas.update(recipe_updates)
    return ideas
    

def sort_entries(cart):
    """Sort a user's shopping cart in alphabetical order.

    Parameters:
        cart (dict): A user's shopping cart dictionary.

    Returns:
        dict: A user's shopping cart sorted in alphabetical order.
    """
    sortedCart = dict(sorted(cart.items()))
    return sortedCart
    


def send_to_store(cart, aisle_mapping):
    """Combine user's order to aisle and refrigeration information.

    Parameters:
        cart (dict): The user's shopping cart dictionary.
        aisle_mapping (dict): The aisle and refrigeration information dictionary.

    Returns:
        dict: The fulfillment dictionary ready to send to store.
    """
    newDict = {}
    for item, value in cart.items():
       if item in aisle_mapping:
           newDict[item] = [value] + aisle_mapping[item]
           
    
    return dict(sorted(newDict.items(), reverse=True))
       
       


def update_store_inventory(fulfillment_cart, store_inventory):
    """Update store inventory levels with user order.

    Parameters:
        fulfillment cart (dict): The fulfillment cart to send to store.
        store_inventory (dict): The stores available inventory.

    Returns:
        dict: The store_inventory updated.
    """
    
   
    for key in fulfillment_cart:
        if key in store_inventory:
            store_inventory[key][0] -= fulfillment_cart[key][0]
            if store_inventory[key][0] == 0:
                store_inventory[key][0] = "Out of Stock"
                
    return store_inventory
            
            
        
    
