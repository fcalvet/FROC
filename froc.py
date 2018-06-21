import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage
from scipy.spatial.distance import euclidean
from scipy.optimize import linear_sum_assignment
import pandas as pd

def computeAssignment(list_detections,list_gt,allowedDistance):
    #the assignment is based on the hungarian algorithm
    #https://docs.scipy.org/doc/scipy-0.18.1/reference/generated/scipy.optimize.linear_sum_assignment.html
    #https://en.wikipedia.org/wiki/Hungarian_algorithm
    
    #build cost matrix
    cost_matrix = np.zeros([len(list_gt),len(list_detections)])
    for i, pointR1 in enumerate(list_gt):
        for j, pointR2 in enumerate(list_detections): 
            cost_matrix[i,j] = euclidean(pointR1,pointR2)
            
    #perform assignment        
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    
    #threshold points too far
    row_ind_thresholded = []
    col_ind_thresholded = []
    for i in range(len(row_ind)):
        if cost_matrix[row_ind[i],col_ind[i]] < allowedDistance:
            row_ind_thresholded.append(row_ind[i])
            col_ind_thresholded.append(col_ind[i])
            
    #compute stats
    P = len(list_gt)
    TP = len(row_ind_thresholded)
    FP = len(list_detections) - TP
            
    return P,TP,FP  

def computeFROCfromListsMatrix(list_ids,list_detections,list_gt,allowedDistance):
    #list_detection: first dimlension: number of images 
    #list_gt: first dimlension: number of images
    
    #get maximum number of detection per image across the dataset
    max_nbr_detections = 0
    for detections in list_detections:
        if len(detections) > max_nbr_detections:
            max_nbr_detections = len(detections)
    
    sensitivity_matrix = pd.DataFrame(columns=list_ids)
    FP_matrix = pd.DataFrame(columns=list_ids)

    for i in range(1,max_nbr_detections):
        sensitivity_per_image = {}
        FP_per_image = {}
        for image_nbr, gt in enumerate(list_gt):
            image_id = list_ids[image_nbr]
            if len(gt) > 0:  #check that ground truth contains at least one annotation
                if i <= len(list_detections[image_nbr]): #if there are detections
                    #compute P, TP, FP per image
                    detections = list_detections[image_nbr][-i]
                    P,TP,FP = computeAssignment(detections,gt,allowedDistance)                
                else:
                    P = len(gt)
                    TP,FP = 0,0
                
                #append results to list
                FP_per_image[image_id] = FP                      
                sensitivity_per_image[image_id] = TP*1./P
            
            elif len(gt) == 0 and i <= len(list_detections[image_nbr]): #if no annotations but detections
                FP = len(list_detections[image_nbr][-i])
                FP_per_image[image_id] = FP 
                sensitivity_per_image[image_id] = None               
         
        sensitivity_matrix = sensitivity_matrix.append(sensitivity_per_image,ignore_index=True)
        FP_matrix = FP_matrix.append(FP_per_image,ignore_index=True)
            
    return sensitivity_matrix, FP_matrix   

def computeFROCfromLists(list_detections,list_gt,allowedDistance):
    #get maximum number of detection per image across the dataset
    max_nbr_detections = 0
    for detections in list_detections:
        if len(detections) > max_nbr_detections:
            max_nbr_detections = len(detections)
    
    sensitivity_list = []
    FPavg_list = []
    sensitivity_list_std = []
    FPavg_list_std = []

    for i in range(max_nbr_detections):
        sensitivity_list_per_image = []
        FP_list_per_image = []
        for image_nbr, gt in enumerate(list_gt):
            if len(gt) > 0:  #check that ground truth contains at least one annotation
                if i <= len(list_detections[image_nbr]): #if there are detections
                    #compute P, TP, FP per image
                    detections = list_detections[image_nbr][-i]
                    P,TP,FP = computeAssignment(detections,gt,allowedDistance)                
                else:
                    P = len(gt)
                    TP,FP = 0,0
                
                #append results to list
                FP_list_per_image.append(FP)                      
                sensitivity_list_per_image.append(TP*1./P)
            
            elif len(gt) == 0 and i <= len(list_detections[image_nbr]): #if no annotations but detections
                FP = len(list_detections[image_nbr][-i])
                FP_list_per_image.append(FP) 
                sensitivity_list_per_image.append(None)               
            
        #average sensitivity and FP over the proba map, for a given threshold
        sensitivity_list.append(np.mean(sensitivity_list_per_image))
        FPavg_list.append(np.mean(FP_list_per_image))
        sensitivity_list_std.append(np.std(sensitivity_list_per_image))
        FPavg_list_std.append(np.std(FP_list_per_image))
            
    return sensitivity_list, FPavg_list, sensitivity_list_std, FPavg_list_std      

def computeConfMatElements(thresholded_proba_map, ground_truth, allowedDistance):
    
    if allowedDistance == 0 and type(ground_truth) == np.ndarray:
        P = np.count_nonzero(ground_truth)
        TP = np.count_nonzero(thresholded_proba_map*ground_truth)
        FP = np.count_nonzero(thresholded_proba_map - (thresholded_proba_map*ground_truth))    
    else:
    
        #reformat ground truth to a list  
        if type(ground_truth) == np.ndarray:
            #convert ground truth binary map to list of coordinates
            labels, num_features = ndimage.label(ground_truth)
            list_gt = ndimage.measurements.center_of_mass(ground_truth, labels, range(1,num_features+1))   
        elif type(ground_truth) == list:        
            list_gt = ground_truth        
        else:
            raise ValueError('ground_truth should be either of type list or ndarray and is of type ' + str(type(ground_truth)))
        
        #reformat thresholded_proba_map to a list
        labels, num_features = ndimage.label(thresholded_proba_map)
        list_proba_map = ndimage.measurements.center_of_mass(thresholded_proba_map, labels, range(1,num_features+1)) 
         
        #compute P, TP and FP  
        P,TP,FP = computeAssignment(list_proba_map,list_gt,allowedDistance)
                                 
    return P,TP,FP
        
def computeFROC(proba_map, ground_truth, allowedDistance, nbr_of_thresholds=40, range_threshold=None):
    #INPUTS
    #proba_map : numpy array of dimension [number of image, xdim, ydim,...], values preferably in [0,1]
    #ground_truth: numpy array of dimension [number of image, xdim, ydim,...], values in {0,1}; or list of coordinates
    #allowedDistance: Integer. euclidian distance distance in pixels to consider a detection as valid (anisotropy not considered in the implementation)  
    #nbr_of_thresholds: Interger. number of thresholds to compute to plot the FROC
    #range_threshold: list of 2 floats. Begining and end of the range of thresholds with which to plot the FROC  
    #OUTPUTS
    #sensitivity_list_treshold: list of average sensitivy over the set of images for increasing thresholds
    #FPavg_list_treshold: list of average FP over the set of images for increasing thresholds
    #threshold_list: list of thresholds
            
    #rescale ground truth and proba map between 0 and 1
    proba_map = proba_map.astype(np.float32)
    proba_map = (proba_map - np.min(proba_map)) / (np.max(proba_map) - np.min(proba_map))
    if type(ground_truth) == np.ndarray:
        #verify that proba_map and ground_truth have the same shape
        if proba_map.shape != ground_truth.shape:
            raise ValueError('Error. Proba map and ground truth have different shapes.')
        
        ground_truth = ground_truth.astype(np.float32)    
        ground_truth = (ground_truth - np.min(ground_truth)) / (np.max(ground_truth) - np.min(ground_truth))
    
    #define the thresholds
    if range_threshold == None:
        threshold_list = (np.linspace(np.min(proba_map),np.max(proba_map),nbr_of_thresholds)).tolist()
    else:
        threshold_list = (np.linspace(range_threshold[0],range_threshold[1],nbr_of_thresholds)).tolist()
    
    sensitivity_list_treshold = []
    FPavg_list_treshold = []
    #loop over thresholds
    for threshold in threshold_list:
        sensitivity_list_proba_map = []
        FP_list_proba_map = []
        #loop over proba map
        for i in range(len(proba_map)):
                       
            #threshold the proba map
            thresholded_proba_map = np.zeros(np.shape(proba_map[i]))
            thresholded_proba_map[proba_map[i] >= threshold] = 1
            
            #save proba maps
#            imageio.imwrite('thresholded_proba_map_'+str(threshold)+'.png', thresholded_proba_map)                   
                   
            #compute P, TP, and FP for this threshold and this proba map
            P,TP,FP = computeConfMatElements(thresholded_proba_map, ground_truth[i], allowedDistance)       
            
            #append results to list
            FP_list_proba_map.append(FP)
            #check that ground truth contains at least one positive
            if (type(ground_truth) == np.ndarray and np.count_nonzero(ground_truth) > 0) or (type(ground_truth) == list and len(ground_truth) > 0):
                sensitivity_list_proba_map.append(TP*1./P)
            
        
        #average sensitivity and FP over the proba map, for a given threshold
        sensitivity_list_treshold.append(np.mean(sensitivity_list_proba_map))
        FPavg_list_treshold.append(np.mean(FP_list_proba_map))    
        
    return sensitivity_list_treshold, FPavg_list_treshold, threshold_list

def plotFROC(x,y,save_path,threshold_list=None):
    plt.figure()
    plt.plot(x,y, 'o-') 
    plt.xlabel('FPavg')
    plt.ylabel('Sensitivity')
    
    #annotate thresholds
    if threshold_list != None:
        #round thresholds
        threshold_list = [ '%.2f' % elem for elem in threshold_list ]            
        xy_buffer = None
        for i, xy in enumerate(zip(x, y)):
            if xy != xy_buffer:                                    
                plt.annotate(str(threshold_list[i]), xy=xy, textcoords='data')
                xy_buffer = xy
    
    plt.savefig(save_path)
    #plt.show()
    
    
    
    
    
    
