%% SoundSight ideal square-array baseline
% This script evaluates the narrowband far-field response of an ideal
% four-microphone square array. It is a geometry sanity check, not a room
% simulation and not measured evidence.

clear;
close all;
clc;

script_dir = fileparts(mfilename('fullpath'));
repo_root = fileparts(fileparts(script_dir));
output_dir = fullfile(repo_root, 'results', 'model', ...
    'square-array-baseline');
if ~isfolder(output_dir)
    mkdir(output_dir);
end

fs_hz = 48000;
sound_speed_mps = 343;
spacing_m = 0.040;
frequencies_hz = [500, 1000, 2000];
steering_deg = 0;
interferer_deg = 90;
scan_deg = -180:1:180;

coordinates_m = (spacing_m / 2) * [
    -1, -1;
     1, -1;
    -1,  1;
     1,  1
];

steering_vector = [cosd(steering_deg); sind(steering_deg)];
response_linear = zeros(numel(frequencies_hz), numel(scan_deg));

for frequency_index = 1:numel(frequencies_hz)
    wave_number = 2 * pi * frequencies_hz(frequency_index) / ...
        sound_speed_mps;
    for angle_index = 1:numel(scan_deg)
        arrival_vector = [cosd(scan_deg(angle_index)); ...
            sind(scan_deg(angle_index))];
        residual_phase = coordinates_m * ...
            (arrival_vector - steering_vector);
        response_linear(frequency_index, angle_index) = abs(mean(exp( ...
            -1i * wave_number * residual_phase)));
    end
end

response_db = 20 * log10(max(response_linear, 10^(-60 / 20)));

figure('Color', 'white', 'Position', [100, 100, 1000, 560]);
plot(scan_deg, response_db, 'LineWidth', 1.8);
grid on;
axes_handle = gca;
set(axes_handle, 'Color', 'white', 'XColor', 'black', 'YColor', 'black', ...
    'GridColor', [0.65, 0.65, 0.65], 'Position', [0.09, 0.12, 0.88, 0.78]);
xlim([-180, 180]);
ylim([-40, 1]);
xticks(-180:30:180);
xlabel('Arrival angle relative to array +x axis (deg)', 'Color', 'black');
ylabel('Normalized response (dB)', 'Color', 'black');
title('Ideal 4-microphone square array, 40 mm spacing, steered to 0 deg', ...
    'Color', 'black');
legend_handle = legend(compose('%d Hz', frequencies_hz), ...
    'Location', 'southwest');
set(legend_handle, 'Color', 'white', 'TextColor', 'black');
exportgraphics(gcf, fullfile(output_dir, ...
    'beam-patterns-40mm.png'), 'Resolution', 180);
close(gcf);

candidate_spacings_m = [0.035, 0.040, 0.050];
comparison_frequency_hz = 1000;
spacing_response_db = zeros(numel(candidate_spacings_m), numel(scan_deg));

for spacing_index = 1:numel(candidate_spacings_m)
    candidate_coordinates_m = (candidate_spacings_m(spacing_index) / 2) * [
        -1, -1;
         1, -1;
        -1,  1;
         1,  1
    ];
    wave_number = 2 * pi * comparison_frequency_hz / sound_speed_mps;
    for angle_index = 1:numel(scan_deg)
        arrival_vector = [cosd(scan_deg(angle_index)); ...
            sind(scan_deg(angle_index))];
        residual_phase = candidate_coordinates_m * ...
            (arrival_vector - steering_vector);
        spacing_response_db(spacing_index, angle_index) = 20 * log10(max( ...
            abs(mean(exp(-1i * wave_number * residual_phase))), ...
            10^(-60 / 20)));
    end
end

figure('Color', 'white', 'Position', [100, 100, 1000, 560]);
plot(scan_deg, spacing_response_db, 'LineWidth', 1.8);
grid on;
axes_handle = gca;
set(axes_handle, 'Color', 'white', 'XColor', 'black', 'YColor', 'black', ...
    'GridColor', [0.65, 0.65, 0.65], 'Position', [0.09, 0.12, 0.88, 0.78]);
xlim([-180, 180]);
ylim([-40, 1]);
xticks(-180:30:180);
xlabel('Arrival angle relative to array +x axis (deg)', 'Color', 'black');
ylabel('Normalized response (dB)', 'Color', 'black');
title('Ideal spacing comparison at 1 kHz, steered to 0 deg', ...
    'Color', 'black');
legend_handle = legend(compose('%d mm', round(candidate_spacings_m * 1000)), ...
    'Location', 'southwest');
set(legend_handle, 'Color', 'white', 'TextColor', 'black');
exportgraphics(gcf, fullfile(output_dir, ...
    'spacing-comparison-1khz.png'), 'Resolution', 180);
close(gcf);

interferer_index = find(scan_deg == interferer_deg, 1);
interferer_attenuation_db = -response_db(:, interferer_index);
attenuation_table = table(frequencies_hz(:), interferer_attenuation_db, ...
    'VariableNames', {'frequency_hz', 'attenuation_at_90deg_db'});
writetable(attenuation_table, fullfile(output_dir, ...
    'attenuation-at-90deg.csv'));

edge_delay_samples = fs_hz * spacing_m / sound_speed_mps;
diagonal_delay_samples = fs_hz * spacing_m * sqrt(2) / sound_speed_mps;
one_sample_broadside_deg = asind(sound_speed_mps / (fs_hz * spacing_m));
five_degree_delay_samples = fs_hz * spacing_m * sind(5) / ...
    sound_speed_mps;

[git_status, git_commit] = system(sprintf( ...
    'git -C "%s" rev-parse HEAD', repo_root));
if git_status ~= 0
    git_commit = 'unavailable';
else
    git_commit = strtrim(git_commit);
end
[git_dirty_status, git_porcelain] = system(sprintf( ...
    'git -C "%s" status --porcelain', repo_root));
if git_dirty_status ~= 0
    working_tree_state = 'unavailable';
elseif isempty(strtrim(git_porcelain))
    working_tree_state = 'clean';
else
    working_tree_state = 'dirty';
end

summary_path = fullfile(output_dir, 'SUMMARY.md');
summary_file = fopen(summary_path, 'w', 'n', 'UTF-8');
cleanup_handle = onCleanup(@() fclose(summary_file));
fprintf(summary_file, '# Ideal square-array baseline\n\n');
fprintf(summary_file, '- Evidence class: analytic floating-point model; not measured data\n');
fprintf(summary_file, '- Git commit at run time: `%s`\n', git_commit);
fprintf(summary_file, '- Working tree at run time: `%s`\n', working_tree_state);
fprintf(summary_file, '- MATLAB: `%s`\n', version);
fprintf(summary_file, '- Reproduce: `matlab -batch "run(''model/matlab/square_array_baseline.m'')"`\n');
fprintf(summary_file, '- Geometry: four ideal omnidirectional microphones on a %.0f mm square\n', spacing_m * 1000);
fprintf(summary_file, '- Sound speed: %.1f m/s; sample rate: %.0f Hz\n\n', ...
    sound_speed_mps, fs_hz);
fprintf(summary_file, '## Numeric checks\n\n');
fprintf(summary_file, '- Edge maximum delay: %.3f samples; legal integer search bound: %d samples\n', ...
    edge_delay_samples, ceil(edge_delay_samples));
fprintf(summary_file, '- Diagonal maximum delay: %.3f samples; legal integer search bound: %d samples\n', ...
    diagonal_delay_samples, ceil(diagonal_delay_samples));
fprintf(summary_file, '- One sample near broadside corresponds to about %.2f deg\n', ...
    one_sample_broadside_deg);
fprintf(summary_file, '- A 5 deg change near broadside corresponds to %.3f sample\n\n', ...
    five_degree_delay_samples);
fprintf(summary_file, '## Ideal 90 deg interferer attenuation\n\n');
fprintf(summary_file, '| Frequency | Attenuation |\n');
fprintf(summary_file, '|---:|---:|\n');
for frequency_index = 1:numel(frequencies_hz)
    fprintf(summary_file, '| %d Hz | %.3f dB |\n', ...
        frequencies_hz(frequency_index), ...
        interferer_attenuation_db(frequency_index));
end
fprintf(summary_file, '\nThese values apply only to the stated ideal narrowband geometry. ');
fprintf(summary_file, 'They are not broadband speech improvement, room performance, or measured SNR.\n');

assert(abs(edge_delay_samples - 5.598) < 0.01);
assert(abs(diagonal_delay_samples - 7.917) < 0.01);
assert(all(abs(interferer_attenuation_db - [0.29; 1.19; 5.16]) < 0.08));

fprintf('PASS: SoundSight ideal square-array baseline generated in %s\n', ...
    output_dir);
