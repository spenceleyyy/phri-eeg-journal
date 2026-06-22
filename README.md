# phri-eeg-journal
This is the EEG pipeline for the phri journal publication :)

# Trigger Pipeline
-----------------------------------------------------------------------------------------------------------------------------------------------
## Componenets
1. **EEG Data** - Lives inside the xdf files - extract as .set -> eeglab
   
2. **Corrected Trigegrs** - Corrected by Aakash to account for any experimentor errors (missed triggers during data collection). Includes start + stop for each portion of the trial. 6/7 = reliable/unrelaible **no fatigue** - 11/12 = reliable/unrelaible **fatigue** - saved in **XDF Time**
     - To correct the triggers:
   
3. **Robot Data** - Robot data is used to create the ERP trigger pipeline by making triggers that correspond to locations the robot visits. Per person, you must account for how the table height was adjusted from the starting position of 103 cm. Table height is saved in the pHRI data colelction logs. Height offset impacts only the **Z** value, and the robot moves in the straight line across the **X** axis.  - saved in **Unix Time**
   - Robot Positions (0 offset/103 cm table Height):
      - **Starting Position - ERP1**: x = .725, y = .449, Z = .398
      - **ERP2**: x = .725, y = .271, Z = .397
      - **ERP3**: x = .725, y = 0.271, Z = .669
      - **ERP4 - Hitting Switch 1**: x = .725, y = .486, Z = .684
      - **ERP5**: x = .725, y = .233, Z = .752
      - **ERP6**: x = .725, y = -.234, Z =.752 

    - _Note that past 3 decimal points, the coords become unreliable_

## Trigger Generation Pipeline - [full_ERP_pipeline.py](full_ERP_pipeline.py)
1. **Convert to common time** The data streams in the research drive (i.e. robotlogs csvs) have the timestamp saved as unix time, making conversions difficult. Instead, extract the data you need from the xdf file, using the xdf timestamp to syncrhonize with corrected triggers.

2. **Put robot data into a dataframe** - gives you data strucutred as:
- xdf_time
- X Position (m)
- Y Position (m)
- Z Position (m)
- unix_time
  
3. **Load corrected triggers** - load in your csv that has the corrected triggers (manually corrected).

4. **Pair trials windows** - allign first trigger as a "start" trigger and the following as a "stop" trigger so you have windows for the code to search for ERP triggers within. **This is NOT an essential componenet, but serves as a quality check of sorts.**

5. **Find and append ERP events to a master trigger set** - based on the above coordinates, search for the ERP triggers in the robot data. **Ensure that you account for the table offset, found in the pHRI logs**
   - While doing this, you must also add times that are readable by EEGLAB. In EEGLAB, time is stored in seconds relative to the start. 

-----------------------------------------------------------------------------------------------------------------------------------------------

# EEG Data

1. **Initial Set up** - For the full processing pipeline, you will need the following packages
   
   - _Required packages_:
     - [EEGLAB](https://eeglab.org/.com)
     - [ERPLAB](https://erpinfo.org/erplab)
     - [load_xdf.m](https://github.com/xdf-modules/xdf-Matlab?utm.com)
       
   - Once downloaded, place these file in you MATLAB file
     
     - Then, in MATLAB, add them to your path:
       
       ```
       addpath('path/to/EEGLAB')
       ```
     - And save the path (so you don't need to do this step every time)
       
       ```
       savepath;
       ```
2. **XDF to .set** - Unfortunately, the software we use to process eeg data (EEGLAB) does not natively accept xdf files, so you will need to convert to a usable file format, using the xdf_to_eeglab_sets.m file.
   
   - To automatically extract, run [xdf_to_eeglab_sets.m](xdf_to_eeglab_sets.m)
     ```
     xdf_to_eeglab_sets.m
     ```
   - When you run this script, the first file exploring pop up needs you to select where the xdf files are. The second pop up allows you to select where the files will output.


## Next, add the new triggers to the XDF file
_If you do not need add new triggers, skip this step. This is necessary when you are (1) adding ERP triggers (like in the present work) or (2) if you have corrected triggers you are using._

1. Use [add_triggers_to_set_files.m](add_triggers_to_set_files.m) to add the triggers to the xdf files.
   ```
   add_triggers_to_set_files.m
   ```
   - This scipt (1) removes the exsisting triggers from a .set file and (2) uploads the new triggers from your csv.
  
**Congratulations, you are ready to preprocess your data!** 
