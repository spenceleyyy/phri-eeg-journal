function xdf_to_eeglab_sets(networkRoot, outRoot)
% xdf_to_eeglab_sets(networkRoot, outRoot)
% - Saves ONLY actiCHamp EEG streams to "<outRoot>/Set Files" (.set + .fdt)
% - Embeds Trigger events (from non-actiCHamp "Trigger"/Markers stream) into each EEG
% - Saves per-EEG Triggers-only dataset (+ CSV) to "<outRoot>/Triggers"
%
% Requires on path: load_xdf.m, EEGLAB (pop_importdata, pop_saveset, eeg_checkset, eeg_emptyset)

    % ---- Folder pickers
    if nargin < 1 || isempty(networkRoot)
        networkRoot = uigetdir(pwd, 'Select folder containing XDF files');
        if isequal(networkRoot, 0), disp('Canceled.'); return; end
    end
    if nargin < 2 || isempty(outRoot)
        outRoot = uigetdir(pwd, 'Select output root folder (where Set Files and Triggers are)');
        if isequal(outRoot, 0), disp('Canceled.'); return; end
    end

    % ---- Dependency check
    mustHave = {'load_xdf','pop_importdata','pop_saveset','eeg_checkset','eeg_emptyset'};
    for f = mustHave
        if exist(f{1}, 'file') ~= 2
            error('Missing dependency on path: %s', f{1});
        end
    end

    % ---- Find files
    files = dir(fullfile(networkRoot, '*.xdf'));
    if isempty(files)
        fprintf('No E*.xdf files in %s\n', networkRoot);
        return;
    end

    % ---- Ensure output subfolders exist
    setDir  = fullfile(outRoot, 'Set Files');
    trigDir = fullfile(outRoot, 'Triggers');
    if ~exist(setDir,  'dir'), mkdir(setDir);  end
    if ~exist(trigDir, 'dir'), mkdir(trigDir); end

    fprintf('Input: %s\nOutput EEG: %s\nOutput Triggers: %s\n', networkRoot, setDir, trigDir);

    for k = 1:numel(files)
        inFile = fullfile(files(k).folder, files(k).name);
        [~, base] = fileparts(inFile);
        fprintf('\n=== Processing %s ===\n', inFile);

        % Load XDF
        streams = load_xdf(inFile, 'HandleClockSynchronization', true, ...
                                     'SynchronizeOnClock', true, ...
                                     'Verbose', false);
        if isempty(streams)
            warning('No streams in %s', inFile);
            continue;
        end

        % Keep ONLY actiCHamp EEG streams
        eegIdx  = find(cellfun(@(s) is_actichamp_eeg(s), streams));

        % Trigger stream: name 'Trigger'/type 'Markers', but EXCLUDE any actiCHamp Markers
        trigIdx = find(cellfun(@(s) is_trigger_stream(s), streams));

        if isempty(eegIdx)
            warning('No actiCHamp EEG streams found in %s', inFile);
        end
        if isempty(trigIdx)
            warning('No Trigger stream (non-actiCHamp) found in %s', inFile);
        end

        % ---------- Save each actiCHamp EEG (with embedded trigger events) ----------
        for ei = 1:numel(eegIdx)
            sEEG = streams{eegIdx(ei)};
            eegTag  = get_actichamp_tag(sEEG, ei);  % amplifier serial ID
            eegBase = sprintf('%s__actiCHamp-%s', base, eegTag);

            [data, nbchan] = to_chans_x_samps(sEEG);
            srate  = get_srate(sEEG);
            labels = get_channel_labels(sEEG, nbchan);
            fprintf('EEG[%d] %s: %d chans x %d samps @ %.3f Hz\n', ei, eegTag, size(data,1), size(data,2), srate);

            EEG = pop_importdata('dataformat','array', ...
                                 'nbchan', nbchan, ...
                                 'data', data, ...
                                 'srate', srate, ...
                                 'xmin', 0);
            if ~isempty(labels) && numel(labels) == nbchan
                EEG.chanlocs = struct('labels', labels(:));
            end

            % Embed Trigger events (from the non-actiCHamp Trigger stream)
            if ~isempty(trigIdx)
                EEG = add_trigger_events(EEG, sEEG.time_stamps(1), streams(trigIdx));
            end

            EEG = eeg_checkset(EEG);

            % Save EEG set+fdt
            pop_saveset(EEG, 'filename', [eegBase '.set'], 'filepath', setDir, 'savemode', 'twofiles');
            fprintf('Saved EEG (+Triggers): %s\n', fullfile(setDir, [eegBase '.set']));

            % ---------- Per-EEG Triggers-only + CSV (aligned to this EEG) ----------
            if ~isempty(trigIdx)
                EEGm  = make_triggers_only_dataset(EEG, sEEG.time_stamps(1), streams(trigIdx));
                mBase = sprintf('%s__actiCHamp-%s__TriggersOnly', base, eegTag);
                pop_saveset(EEGm, 'filename', [mBase '.set'], 'filepath', trigDir, 'savemode', 'twofiles');
                fprintf('Saved Triggers-Only: %s\n', fullfile(trigDir, [mBase '.set']));

                [absT, lat, lab] = collect_trigger_events(EEG, sEEG.time_stamps(1), streams(trigIdx));
                if ~isempty(absT)
                    T = table(absT(:), lat(:), string(lab(:)), ...
                              'VariableNames', {'Timestamp','Latency','Label'});
                    writetable(T, fullfile(trigDir, sprintf('%s__actiCHamp-%s__Triggers.csv', base, eegTag)));
                    fprintf('Saved trigger CSV: %s\n', fullfile(trigDir, sprintf('%s__actiCHamp-%s__Triggers.csv', base, eegTag)));
                end
            end
        end
    end
end

% ================= filters & helpers =================

function tf = is_actichamp_eeg(s)
    name = lower(coalesce_str(safeget(s.info, {'name'}, ''), ''));
    typ  = lower(coalesce_str(safeget(s.info, {'type'}, ''), ''));
    tf = contains(name, 'actichamp') && contains(typ, 'eeg');
end

function tf = is_trigger_stream(s)
    % True for 'Trigger' / Markers streams, but explicitly skip actiCHamp marker streams
    name = lower(strtrim(coalesce_str(safeget(s.info, {'name'}, ''), '')));
    typ  = lower(coalesce_str(safeget(s.info, {'type'}, ''), ''));
    tf = (strcmp(name,'trigger') || strcmp(name,'triggers') || contains(typ,'marker'));
    tf = tf && ~contains(name, 'actichamp');  % exclude actiCHamp Markers streams
end

function tag = get_actichamp_tag(s, fallbackIdx)
% Extract stable actiCHamp identifier (prefer serial), fallback to UID/SourceID/name/index.
    candidates = strings(0);
    candidates(end+1) = string(safeget(s.info, {'desc','manufacturer','serial_number'}, ''));
    candidates(end+1) = string(safeget(s.info, {'desc','hardware_serial'}, ''));
    candidates(end+1) = string(safeget(s.info, {'source_id'}, ''));
    candidates(end+1) = string(safeget(s.info, {'uid'}, ''));
    candidates(end+1) = string(safeget(s.info, {'name'}, ''));

    % Try specific 'actiCHamp-<digits>'
    for c = candidates(:).'
        c = strtrim(c);
        if strlength(c)==0, continue; end
        m = regexp(lower(c), 'actichamp[-_\s]*([0-9]{5,})', 'tokens', 'once');
        if ~isempty(m), tag = m{1}; return; end
    end
    % Else take the longest 5+ digit run
    for c = candidates(:).'
        c = strtrim(c);
        if strlength(c)==0, continue; end
        m = regexp(c, '([0-9]{5,})', 'tokens', 'once');
        if ~isempty(m), tag = m{1}; return; end
    end
    % Else short hash-ish suffix of uid/source_id
    uid = string(safeget(s.info, {'uid'}, ''));
    sid = string(safeget(s.info, {'source_id'}, ''));
    anyid = char(uid); if isempty(anyid), anyid = char(sid); end
    if ~isempty(anyid)
        anyid = regexprep(anyid, '[^A-Za-z0-9]', '');
        if ~isempty(anyid)
            tag = anyid(max(1,end-6):end);
            return;
        end
    end
    % Last resort
    if nargin<2 || isempty(fallbackIdx), fallbackIdx = 1; end
    tag = sprintf('EEG%02d', fallbackIdx);
end

function [data, nbchan] = to_chans_x_samps(stream)
% Orient XDF numeric data to [channels x samples] using channel_count hint.
    ts = stream.time_series;

    nchan_hint = str2double(safeget(stream.info, {'channel_count'}, 'NaN'));
    if isnan(nchan_hint) || nchan_hint <= 0
        nchan_hint = [];
    end

    if isnumeric(ts)
        data = double(ts);
    elseif iscell(ts) && isnumeric_safe_cell(ts)
        data = double(cell2mat(ts(:)).');  % 1 x N
    else
        error('Non-numeric time_series encountered where numeric was expected.');
    end

    if ~isempty(nchan_hint)
        if size(data,1) == nchan_hint
            % ok
        elseif size(data,2) == nchan_hint
            data = data.';  % transpose to chans x samps
        else
            if size(data,1) > size(data,2) && size(data,2) > 1
                data = data.'; 
            end
        end
    else
        if size(data,1) > size(data,2) && size(data,2) > 1
            data = data.'; 
        end
    end

    if size(data,1) > size(data,2) && size(data,2) > 1
        data = data.'; 
    end

    nbchan = size(data,1);
end

function srate = get_srate(s)
    % Try metadata first
    srate = str2double(safeget(s.info, {'effective_srate'}, 'NaN'));
    if isnan(srate) || srate <= 0
        srate = str2double(safeget(s.info, {'nominal_srate'}, 'NaN'));
    end
    % Fallback: infer from timestamps
    if (isnan(srate) || srate <= 0 || ~isfinite(srate)) ...
            && isfield(s,'time_stamps') && numel(s.time_stamps) > 10
        ts = double(s.time_stamps);
        dt = diff(ts);
        dt = dt(isfinite(dt) & dt > 0);
        if ~isempty(dt)
            srate = 1 / median(dt);
        end
    end
    if isnan(srate) || srate <= 0 || ~isfinite(srate)
        error('Could not determine sampling rate for stream "%s".', ...
              coalesce_str(safeget(s.info,{'name'},''),'(unnamed)'));
    end
end

function labels = get_channel_labels(s, nbchan)
    labels = {};
    try
        ch = safeget(s.info, {'desc','channels','channel'}, []);
        if isstruct(ch) && numel(ch) >= 1
            labels = arrayfun(@(c,i) coalesce_str(safeget(c, {'label'}, sprintf('CH%03d', i))), ...
                              ch, (1:numel(ch))', 'UniformOutput', false);
        end
    catch
        labels = {};
    end
    if isempty(labels) || numel(labels) ~= nbchan
        labels = arrayfun(@(i) sprintf('CH%03d', i), 1:nbchan, 'UniformOutput', false);
    end
end

function EEG = add_trigger_events(EEG, t0, trigStreams)
    % Add events from Trigger stream(s) (non-actiCHamp Markers) directly into EEG.event
    evs = struct('latency', {}, 'type', {});
    evCount = 0;
    for mi = 1:numel(trigStreams)
        ms = trigStreams{mi};
        ts = ms.time_stamps;
        payload = ms.time_series;
        for j = 1:numel(ts)
            latency = 1 + round((ts(j) - t0) * EEG.srate);
            if latency >= 1 && latency <= EEG.pnts
                evCount = evCount + 1;
                evs(evCount).latency = latency; %#ok<AGROW>
                evs(evCount).type    = as_event_label(payload, j);
            end
        end
    end
    if ~isempty(evs)
        if ~isfield(EEG,'event') || isempty(EEG.event)
            EEG.event = evs;
        else
            EEG.event = [EEG.event evs]; %#ok<AGROW>
        end
        EEG = eeg_checkset(EEG, 'eventconsistency');
    end
end

function EEGm = make_triggers_only_dataset(EEGref, t0, trigStreams)
% 1-channel zeros aligned to EEG timeline; events populated from Trigger stream(s).
    EEGm = eeg_emptyset();
    EEGm.nbchan = 1;
    EEGm.srate  = EEGref.srate;
    EEGm.pnts   = EEGref.pnts;
    EEGm.trials = 1;
    EEGm.xmin   = 0;
    EEGm.xmax   = (EEGm.pnts - 1) / EEGm.srate;
    EEGm.data   = zeros(1, EEGm.pnts, 'double');
    EEGm.chanlocs = struct('labels','TRIG');
    EEGm.setname = [EEGref.setname '__TriggersOnly'];

    EEGm.event = [];
    evCount = 0;
    for mi = 1:numel(trigStreams)
        ms = trigStreams{mi};
        ts = ms.time_stamps;
        payload = ms.time_series;
        for j = 1:numel(ts)
            latency = 1 + round((ts(j) - t0) * EEGm.srate);
            if latency >= 1 && latency <= EEGm.pnts
                evCount = evCount + 1;
                EEGm.event(evCount).latency = latency; %#ok<AGROW>
                EEGm.event(evCount).type    = as_event_label(payload, j);
            end
        end
    end
    EEGm = eeg_checkset(EEGm, 'eventconsistency');
end

function [absT, latency, label] = collect_trigger_events(EEGref, t0, trigStreams)
% Returns vectors for CSV: absolute timestamps (sec), EEG-sample latency, and labels.
    absT    = [];
    latency = [];
    label   = {};
    for mi = 1:numel(trigStreams)
        ms = trigStreams{mi};
        ts = ms.time_stamps;
        payload = ms.time_series;
        for j = 1:numel(ts)
            lat = 1 + round((ts(j) - t0) * EEGref.srate);
            if lat >= 1 && lat <= EEGref.pnts
                absT(end+1)    = ts(j); %#ok<AGROW>
                latency(end+1) = lat;    %#ok<AGROW>
                label{end+1}   = as_event_label(payload, j); %#ok<AGROW>
            end
        end
    end
end

function val = safeget(s, path, defaultVal)
    val = defaultVal;
    try
        cur = s;
        for i = 1:numel(path)
            key = path{i};
            if isstruct(cur) && isfield(cur, key)
                cur = cur.(key);
            elseif iscell(cur) && ~isempty(cur)
                cur = cur{1};
                if isstruct(cur) && isfield(cur, key)
                    cur = cur.(key);
                else
                    cur = defaultVal; break;
                end
            else
                cur = defaultVal; break;
            end
        end
        if iscell(cur) && numel(cur) == 1, cur = cur{1}; end
        val = cur;
    catch
        val = defaultVal;
    end
end

function s = coalesce_str(varargin)
    s = '';
    for i = 1:nargin
        v = varargin{i};
        if ischar(v) || (isstring(v) && isscalar(v))
            if strlength(string(v)) > 0
                s = char(string(v));
                return;
            end
        end
    end
end

function lbl = as_event_label(payload, j)
    try
        v = payload(:, j);
        if iscell(v),   v = v{1}; end
        if isstring(v), lbl = char(v); return; end
        if ischar(v),   lbl = v;      return; end
        if isnumeric(v), lbl = sprintf('%.0f', v); return; end
    catch
    end
    lbl = 'marker';
end

function tf = isnumeric_safe_cell(ts)
    tf = iscell(ts) && ~isempty(ts);
    if tf
        try
            a = cellfun(@(x) isnumeric(x) && isscalar(x), ts);
            tf = all(a(:));
        catch
            tf = false;
        end
    end
end
