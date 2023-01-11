#!/usr/bin/env python

"""
A driver for interseismic velocity inversion for fault slip rates.
Relative to a specific station instead of a reference frame.
Mostly research code.  It is included in the repo as an example of what to do with this toolbox.
Depends on Humboldt Bay project code for some functions. It will not work on a different general system.
"""

import numpy as np
import scipy.optimize
import sys
import Elastic_stresses_py.PyCoulomb.fault_slip_object as library
import Elastic_stresses_py.PyCoulomb as PyCoulomb
import Geodesy_Modeling.src.Inversion.inversion_tools as inv_tools
import Geodesy_Modeling.src.Inversion.readers as readers
import Elastic_stresses_py.PyCoulomb.disp_points_object as dpo
sys.path.append("/Users/kmaterna/Documents/B_Research/Mendocino_Geodesy/Humboldt/_Project_Code");  # add local code
import humboldt_readers as HR  # Also had to add into pycharm project settings.
sys.path.append(".");  # add local code
import humboldt_inversion_driver as local


def correct_for_far_field_terms(exp_dict, obs_disp_points, refpt):
    """
    Velocity corrections, to set boundary conditions, some from Pollitz & Evans, 2017.
    """
    for correction in exp_dict["corrections"]:
        correction_dps = local.reader_dictionary[correction["type"]](correction["file"], exp_dict["lonlatfile"]);
        correction_dps = dpo.utilities.mult_disp_points_by(correction_dps, correction["scale"]);
        refdpo = dpo.utilities.extract_particular_station_from_list(correction_dps, refpt[0], refpt[1]);  # SACR
        correction_dps = dpo.utilities.subtract_reference_from_disp_points(correction_dps, refdpo);
        if correction["type"] == "csz":
            obs_disp_points = dpo.utilities.subtract_disp_points(obs_disp_points, correction_dps, tol=0.001,
                                                                 target='horizontal');
        else:
            obs_disp_points = dpo.utilities.subtract_disp_points(obs_disp_points, correction_dps, tol=0.001);
    return obs_disp_points;


def read_fault_gf_elements(exp_dict, refpt):
    """
    Input: a config dictionary
    Return: a list of inversion_tools.GF_elements,
    With green's functions RELATIVE TO A PARTICULAR POINT
    which are the building blocks for the columns of the Green's function inversion.
    Read a list of green's functions for the modeled faults in this experiment.  One for each model parameter.
    """
    gf_elements = [];  # building blocks for columns in the Green's matrix
    for i in range(len(exp_dict["exp_faults"])):  # for each fault
        fault_name = exp_dict["exp_faults"][i];
        if fault_name == "CSZ_dist":  # Reading for distributed CSZ patches as unit slip.
            one_patch_dps, csz_patches, maxslip = readers.read_distributed_GF(exp_dict["faults"]["CSZ"]["GF"],
                                                                              exp_dict["faults"]["CSZ"]["geometry"],
                                                                              exp_dict["lonlatfile"], unit_slip=True,
                                                                              latlonbox=(-127, -120, 38, 44.5));
            for gf_disp_points, patch, max0 in zip(one_patch_dps, csz_patches, maxslip):
                refdpo = dpo.utilities.extract_particular_station_from_list(gf_disp_points, refpt[0], refpt[1]);  # SACR
                gf_disp_points = dpo.utilities.subtract_reference_from_disp_points(gf_disp_points, refdpo);
                one_gf_element = inv_tools.GF_element(disp_points=gf_disp_points, fault_name=fault_name,
                                                      fault_dict_list=[patch],
                                                      lower_bound=exp_dict["faults"]["CSZ"]["slip_min"],
                                                      upper_bound=max0*100,  # max slip from geometry, in units of cm
                                                      slip_penalty_flag=1, units='cm/yr', points=[]);
                gf_elements.append(one_gf_element);
        else:  # Reading for LSF, MRF, other fault cases
            fault_gf = exp_dict["faults"][fault_name]["GF"];
            fault_geom = exp_dict["faults"][fault_name]["geometry"];
            temp, _ = library.file_io.io_static1d.read_static1D_source_file(fault_geom, headerlines=1);
            mod_disp_points = library.file_io.io_static1d.read_static1D_output_file(fault_gf, exp_dict["lonlatfile"]);
            refdpo = dpo.utilities.extract_particular_station_from_list(mod_disp_points, refpt[0], refpt[1]);  # SACR
            mod_disp_points = dpo.utilities.subtract_reference_from_disp_points(mod_disp_points, refdpo);
            fault_points = np.loadtxt(exp_dict["faults"][fault_name]["points"]);  # fault trace
            one_gf_element = inv_tools.GF_element(disp_points=mod_disp_points, fault_name=fault_name,
                                                  fault_dict_list=temp,
                                                  lower_bound=exp_dict["faults"][fault_name]["slip_min"],
                                                  upper_bound=exp_dict["faults"][fault_name]["slip_max"],
                                                  slip_penalty_flag=0, units='cm/yr', points=fault_points);
            gf_elements.append(one_gf_element);
    return gf_elements;


def run_humboldt_inversion(config_file):
    # Starting program.  Configure stage
    exp_dict = local.configure(config_file);
    refpt = [-121.354240, 38.655000];

    # # INPUT stage: Read obs velocities as cc.Displacement_Points
    obs_disp_points = HR.read_all_data_table(exp_dict["data_file"]);   # all 783 points
    reference_station = dpo.utilities.extract_particular_station_from_list(obs_disp_points, refpt[0], refpt[1]);  # SACR
    obs_disp_points = dpo.utilities.subtract_reference_from_disp_points(obs_disp_points, reference_station);
    obs_disp_points = correct_for_far_field_terms(exp_dict, obs_disp_points, refpt);  # needed from Fred's work
    # Experimental options (ex: dpo.utilities.filter_to_meas_type(obs_disp_points, 'continuous'))
    obs_disp_points = local.remove_near_fault_points(obs_disp_points, exp_dict["faults"]["Maacama"]["points"])
    obs_disp_points = local.remove_near_fault_points(obs_disp_points, exp_dict["faults"]["BSF"]["points"])
    obs_disp_points = dpo.utilities.filter_to_exclude_bounding_box(obs_disp_points, [-121.6, -121.4, 40.4, 40.55]);
    obs_disp_points = dpo.utilities.filter_by_bounding_box(obs_disp_points, [-127, -121, 38.5, 40.1]);  # exp. step

    # INPUT stage: Read GF models based on the configuration parameters
    gf_elements = read_fault_gf_elements(exp_dict, refpt);  # list of GF_elements for each fault-related column of G.

    # COMPUTE STAGE: PREPARE ROTATION GREENS FUNCTIONS AND LEVELING OFFSET
    # gf_elements_rotation = inv_tools.get_GF_rotation_elements(obs_disp_points);  # 3 elements: rot_x, rot_y, rot_z
    # gf_elements = gf_elements + gf_elements_rotation;  # add rotation elements to matrix
    gf_element_lev = inv_tools.get_GF_leveling_offset_element(obs_disp_points);  # 1 element: lev reference frame
    gf_elements = gf_elements + gf_element_lev;

    # COMPUTE STAGE: Pairing is necessary in case you've filtered out any observations along the way.
    paired_obs, paired_gf_elements = inv_tools.pair_gf_elements_with_obs(obs_disp_points, gf_elements);

    inv_tools.visualize_GF_elements(paired_gf_elements, exp_dict["outdir"], exclude_list='all');

    # COMPUTE STAGE: INVERSE.  Reduces certain points to only-horizontal, only-vertical, etc.
    list_of_gf_columns = [];
    for paired_gf in paired_gf_elements:
        G_one_col = inv_tools.buildG_column(paired_gf.disp_points, paired_obs);  # for one fault model parameter
        list_of_gf_columns.append(G_one_col);
    G = np.concatenate(tuple(list_of_gf_columns), axis=1);

    # Build observation vector
    obs, _sigmas = inv_tools.build_obs_vector(paired_obs);
    sigmas = np.ones(np.shape(obs));  # placeholder until uncertainty on tide gages is determined.
    G /= sigmas[:, None];
    weighted_obs = obs / sigmas;

    # Add optional smoothing penalty, overwriting old variables
    if 'smoothing' in exp_dict.keys():
        G, weighted_obs, sigmas = inv_tools.build_smoothing(paired_gf_elements, ('CSZ_dist'),
                                                            exp_dict["smoothing"], G, weighted_obs, sigmas);
    # Add optional slip weighting penalty, overwriting old variables
    if 'slip_penalty' in exp_dict.keys():
        G, weighted_obs, sigmas = inv_tools.build_slip_penalty(paired_gf_elements,
                                                               exp_dict["slip_penalty"], G, weighted_obs, sigmas);

    # Money line: Constrained inversion
    lb = [x.lower_bound for x in paired_gf_elements];
    ub = [x.upper_bound for x in paired_gf_elements];
    response = scipy.optimize.lsq_linear(G, weighted_obs, bounds=(lb, ub), max_iter=1500, method='bvls');
    M_opt = response.x;  # parameters of best-fitting model
    print(response.message);
    if response.message == "The maximum number of iterations is exceeded.":
        print("Maximum number of iterations exceeded. Cannot trust this inversion. Exiting");
        sys.exit(0);

    # Make forward predictions
    M_rot_only, M_no_rot = inv_tools.unpack_model_of_rotation_only(M_opt, [x.fault_name for x in paired_gf_elements]);
    M_csz = inv_tools.unpack_model_of_target_param(M_opt, [x.fault_name for x in paired_gf_elements], 'CSZ_dist');
    model_disp_points = inv_tools.forward_disp_points_predictions(G, M_opt, sigmas, paired_obs);
    rot_modeled_pts = inv_tools.forward_disp_points_predictions(G, M_rot_only, sigmas, paired_obs);
    norot_modeled_pts = inv_tools.forward_disp_points_predictions(G, M_no_rot, sigmas, paired_obs);
    csz_modeled_pts = inv_tools.forward_disp_points_predictions(G, M_csz, sigmas, paired_obs);

    # Output stage
    fault_dict_lists = [item.fault_dict_list for item in paired_gf_elements];
    rms_mm, rms_chi2 = inv_tools.rms_from_model_pred_vector(G.dot(M_opt) * sigmas, weighted_obs * sigmas, sigmas);
    rms_title = "RMS: %f mm/yr" % rms_mm;
    print(" ", rms_title);
    residual_pts = dpo.utilities.subtract_disp_points(paired_obs, model_disp_points);
    PyCoulomb.io_additionals.write_disp_points_results(model_disp_points, exp_dict["outdir"] + '/model_pred_file.txt');
    PyCoulomb.io_additionals.write_disp_points_results(residual_pts, exp_dict["outdir"] + '/resid_file.txt');
    PyCoulomb.io_additionals.write_disp_points_results(paired_obs, exp_dict["outdir"] + '/simple_obs_file.txt');
    inv_tools.write_model_params(M_opt, rms_mm, exp_dict["outdir"] + '/' + exp_dict["model_file"],
                                 paired_gf_elements);
    inv_tools.write_summary_params(M_opt, rms_mm, exp_dict["outdir"] + '/model_results_human.txt',
                                   paired_gf_elements,
                                   ignore_faults=['CSZ_dist'], message=response.message);
    inv_tools.write_fault_traces(M_opt, paired_gf_elements, exp_dict["outdir"] + '/fault_output.txt',
                                 ignore_faults=['CSZ_dist', 'x_rot', 'y_rot', 'z_rot', 'lev_offset', 'LSFRev']);
    readers.write_csz_dist_fault_patches(fault_dict_lists, M_opt, exp_dict["outdir"] + '/csz_model.gmt');
    inv_tools.view_full_results(exp_dict, paired_obs, model_disp_points, residual_pts, rot_modeled_pts,
                                norot_modeled_pts, rms_title, region=[-127, -119.7, 37.7, 43.5]);
    library.plot_fault_slip.map_source_slip_distribution([], exp_dict["outdir"] + "/csz_only_pred.png",
                                                         disp_points=csz_modeled_pts, region=[-127, -119.7, 37.7, 43.5],
                                                         scale_arrow=(1.0, 0.010, "1 cm/yr"),
                                                         v_labeling_interval=0.001)
    library.plot_fault_slip.plot_data_model_residual(exp_dict["outdir"] + "/results.png", paired_obs,
                                                     model_disp_points, residual_pts, [-126, -119.7, 37.7, 43.3],
                                                     scale_arrow=(0.5, 0.020, "2 cm"), v_labeling_interval=0.003,
                                                     fault_dict_list=[], rms=rms_mm);
    return;


if __name__ == "__main__":
    config_file = sys.argv[1];  # take config file from runstring.
    run_humboldt_inversion(config_file);
