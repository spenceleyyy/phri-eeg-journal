function add_triggers_to_set_files()

setRoot  = '/Users/hotcocks/Desktop/pHRIEEGJ/Corrected Data/Batch_Output';
trigRoot = '/Users/hotcocks/Desktop/pHRIEEGJ/Corrected Data/Batch_Output';

mustHave = {'pop_loadset','pop_saveset','eeg_checkset'};
for i = 1:numel(mustHave)
    if exist(mustHave{i}, 'file') ~= 2
        error('Missing EEGLAB dependency on path: %s', mustHave{i});
    end
end

allSetFiles = dir(fullfile(setRoot, '**', '*.set'));
setFiles = [];

for i = 1:numel(allSetFiles)
    fname = allSetFiles(i).name;
    fpath = allSetFiles(i).folder;

    if contains(fname, 'TriggersOnly', 'IgnoreCase', true)
        continue;
    end

    if contains(fpath, 'Set with triggers', 'IgnoreCase', true)
        continue;
    end

    if ~contains(fpath, [filesep 'Set Files'], 'IgnoreCase', true)
        continue;
    end

    setFiles = [setFiles; allSetFiles(i)];
end

if isempty(setFiles)
    fprintf('No valid EEG .set files found in:\n%s\n', setRoot);
    return;
end

fprintf('Found %d EEG .set files.\n', numel(setFiles));

for k = 1:numel(setFiles)
    [~, setBase] = fileparts(setFiles(k).name);

    fprintf('\n=== Processing EEG file %s ===\n', setFiles(k).name);

    trigCsv = find_matching_trigger_csv(trigRoot, setBase);

    if isempty(trigCsv)
        warning('No matching trigger CSV found for %s. Skipping.', setFiles(k).name);
        continue;
    end

    fprintf('Using trigger CSV: %s\n', trigCsv);

    EEG = pop_loadset('filename', setFiles(k).name, ...
                      'filepath', setFiles(k).folder);

    EEG.event = [];

    T = readtable(trigCsv);

    requiredCols = {'eeglab_latency','event_label'};
    if ~all(ismember(requiredCols, T.Properties.VariableNames))
        warning('Trigger CSV missing eeglab_latency and event_label. Skipping %s.', trigCsv);
        continue;
    end

    fprintf('Events available in CSV: %d\n', height(T));

    nAdded = 0;

    for r = 1:height(T)
        lat = round(T.eeglab_latency(r));
        labelStr = string(T.event_label(r));

        if ismissing(labelStr) || strlength(labelStr) == 0
            continue;
        end

        if isnan(lat) || lat < 1 || lat > EEG.pnts
            continue;
        end

        nAdded = nAdded + 1;
        EEG.event(nAdded).latency = lat;
        EEG.event(nAdded).type = char(labelStr);

        if ismember('source', T.Properties.VariableNames)
            srcStr = string(T.source(r));
            if ~ismissing(srcStr) && strlength(srcStr) > 0
                EEG.event(nAdded).source = char(srcStr);
            end
        end

        if ismember('distance_m', T.Properties.VariableNames) && ...
           ~ismissing(T.distance_m(r)) && ~isnan(T.distance_m(r))
            EEG.event(nAdded).distance_m = T.distance_m(r);
        end
    end

    if nAdded == 0
        warning('No valid trigger events added for %s.', setFiles(k).name);
        continue;
    end

    EEG = eeg_checkset(EEG, 'eventconsistency');

    participantFolder = fileparts(setFiles(k).folder);
    thisOutFolder = fullfile(participantFolder, 'Set with triggers');

    if ~exist(thisOutFolder, 'dir')
        mkdir(thisOutFolder);
    end

    outName = [setBase '_AllTriggers.set'];

    pop_saveset(EEG, ...
        'filename', outName, ...
        'filepath', thisOutFolder, ...
        'savemode', 'twofiles');

    fprintf('Added %d total events to EEG data file.\n', nAdded);
    fprintf('Saved: %s\n', fullfile(thisOutFolder, outName));
end

fprintf('\nDone.\n');

end


function trigCsv = find_matching_trigger_csv(trigRoot, setBase)

trigCsv = '';
allCsv = dir(fullfile(trigRoot, '**', '*.csv'));

cleanBase = setBase;
cleanBase = erase(cleanBase, '_withTriggers');
cleanBase = erase(cleanBase, '_ERPTriggers');
cleanBase = erase(cleanBase, '_AllTriggers');

participantID = regexp(cleanBase, 'PHRIE\d+(_2)?', 'match', 'once');

if isempty(participantID)
    return;
end

baseParticipantID = erase(participantID, '_2');

preferredNames = {
    [participantID '_combined_corrected_and_erp_triggers_COMMON_TIME.csv']
    [baseParticipantID '_combined_corrected_and_erp_triggers_COMMON_TIME.csv']
};

for p = 1:numel(preferredNames)
    for i = 1:numel(allCsv)
        if strcmpi(allCsv(i).name, preferredNames{p})
            trigCsv = fullfile(allCsv(i).folder, allCsv(i).name);
            return;
        end
    end
end

end