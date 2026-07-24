def is_armstrong_number(number):
    calculo = 0
    for items in str(number):
        calculo += (int(items)**len(str(number)))
  
    if calculo == number:
        return True
    else: 
        return False
            
        
    
        
        
