%% SoundSight historical square-array geometry checks
% Numerical reference for the old 40 mm square array, not the current
% tetrahedral array and not a measurement of room performance.
fs_hz = 48000;
sound_speed_mps = 343;
spacing_m = 0.040;
edge_delay_samples = fs_hz * spacing_m / sound_speed_mps;
diagonal_delay_samples = fs_hz * spacing_m * sqrt(2) / sound_speed_mps;
one_sample_broadside_deg = asind(sound_speed_mps / (fs_hz * spacing_m));
five_degree_delay_samples = fs_hz * spacing_m * sind(5) / ...
    sound_speed_mps;

assert(abs(edge_delay_samples - 5.598) < 0.01);
assert(abs(diagonal_delay_samples - 7.917) < 0.01);
fprintf('Edge maximum delay: %.3f samples\n', edge_delay_samples);
fprintf('Diagonal maximum delay: %.3f samples\n', diagonal_delay_samples);
fprintf('One-sample broadside angle: %.2f deg\n', one_sample_broadside_deg);
fprintf('Five-degree delay: %.3f sample\n', five_degree_delay_samples);
fprintf('PASS: historical square-array geometry checks\n');
