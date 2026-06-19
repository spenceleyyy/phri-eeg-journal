# phri-eeg-journal
This is the EEG pipeline for the phri journal publication :)

## Componenets
1. **EEG Data** - Lives inside the xdf files - extract as .set -> eeglab
   
2. **Corrected Trigegrs** - Corrected by Aakash to account for any experimentor errors (missed triggers during data collection). Includes start + stop for each portion of the trial. 6/7 = reliable/unrelaible **no fatigue** - 11/12 = reliable/unrelaible **fatigue** - saved in **XDF Time**
   
3. **Robot Data** - Robot data is used to create the ERP trigger pipeline by making triggers that correspond to locations the robot visits. Per person, you must account for how the table height was adjusted from the starting position of 103 cm. Table height is saved in the pHRI data colelction logs. Height offset impacts only the **Z** value, and the robot moves in the straight line across the **X** axis.  - saved in **Unix Time**
   - Robot Positions (0 offset/103 cm table Height):
      - **Starting Position - ERP1**: x = .725, y = .449, Z = .3975
      - **ERP2**: x = .725, y = .232, Z = .397
      - **ERP3**: x = .725, y = 0.232, Z = .684
      - **ERP4 - Hitting Switch 1**: x = .725, y = .486, Z = .684
      - **ERP5**: x = .725, y = .233, Z = .752
      - **ERP6**: x = .725, y = -.234, Z =.752 

    - _Note that past 3 decimal points, the coords become unreliable_

## Trigger Pipeline
1. Since you have the 

### 
