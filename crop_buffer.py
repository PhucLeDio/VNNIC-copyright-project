import cv2

def main():
    img = cv2.imread("flow_v2.png")
    
    # We want to crop the cylinder. Let's try x from 550 to 920, y from 1180 to 1260
    # Let's crop x=560, y=1190, w=360, h=65
    crop = img[1190:1255, 560:920]
    cv2.imwrite("slide/images/buffer.png", crop)
    
    # Also save the wide Step 4 as step4.png
    step4 = img[1280:1280+550, 580:580+790]
    cv2.imwrite("slide/images/step4.png", step4)
    
    # Also save bottom_0 as step5.png
    step5 = img[1817:1817+250, 843:843+293]
    cv2.imwrite("slide/images/step5.png", step5)

if __name__ == "__main__":
    main()
