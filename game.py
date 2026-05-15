import random
n=input("enter your choice")
for i in range(1,4):
    num =random.randint(1,3)
    if i == 1:
        print("scissors")
        break;
    elif i==2:
         print("stone")
         break;
    else :
        print("paper")
        break;
