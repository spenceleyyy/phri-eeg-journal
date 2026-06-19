# phri-eeg-journal
This is the EEG pipeline for the phri journal publication :)

# Trigger Pipeline
-----------------------------------------------------------------------------------------------------------------------------------------------
## Componenets
1. **EEG Data** - Lives inside the xdf files - extract as .set -> eeglab
   
2. **Corrected Trigegrs** - Corrected by Aakash to account for any experimentor errors (missed triggers during data collection). Includes start + stop for each portion of the trial. 6/7 = reliable/unrelaible **no fatigue** - 11/12 = reliable/unrelaible **fatigue** - saved in **XDF Time**
   
3. **Robot Data** - Robot data is used to create the ERP trigger pipeline by making triggers that correspond to locations the robot visits. Per person, you must account for how the table height was adjusted from the starting position of 103 cm. Table height is saved in the pHRI data colelction logs. Height offset impacts only the **Z** value, and the robot moves in the straight line across the **X** axis.  - saved in **Unix Time**
   - Robot Positions (0 offset/103 cm table Height):
      - **Starting Position - ERP1**: x = .725, y = .449, Z = .398
      - **ERP2**: x = .725, y = .271, Z = .397
      - **ERP3**: x = .725, y = 0.271, Z = .669
      - **ERP4 - Hitting Switch 1**: x = .725, y = .486, Z = .684
      - **ERP5**: x = .725, y = .233, Z = .752
      - **ERP6**: x = .725, y = -.234, Z =.752 

    - _Note that past 3 decimal points, the coords become unreliable_

## Trigger Pipeline - full_ERP_pipeline.py
1. **Convert to common time** The data streams in the research drive (i.e. robotlogs csvs) have the timestamp saved as unix time, making conversions difficult. Instead, extract the data you need from the xdf file, using the xdf timestamp to syncrhonize with corrected triggers.

2. **Put robot data into a dataframe** - gives you data strucutred as:
- xdf_time
- X Position (m)
- Y Position (m)
- Z Position (m)
- unix_time
  
3. **Load corrected triggers** - load in your csv that has the corrected triggers (manually corrected).

4. **Pair trials windows** - allign first trigger as a "start" trigger and the following as a "stop" trigger so you have windows for the code to search for ERP triggers within.

5. **Find and append ERP events to a master trigger set** - based on the above coordinates, search for the ERP triggers in the robot data. **Ensure that you account for the table offset, found in the pHRI logs**

-----------------------------------------------------------------------------------------------------------------------------------------------
