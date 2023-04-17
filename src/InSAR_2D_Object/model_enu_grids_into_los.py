"""
Project 3 grd files of modeled east/north/up deformation into the LOS of an assumed satellite flight.
Simple calculation - single incidence angle for now.
"""

import Geodesy_Modeling.src.InSAR_2D_Object as InSAR_2D_Object


def parse_config(params_provided):
    defaults = {  # REQUIRED PARAMETERS
              'east_grdfile': 'east.grd',  # with units of meters by default
              'north_grdfile': 'north.grd',  # with units of meters by default
              'up_grdfile': 'vert.grd',  # with units of meters by default
              'flight_direction': 190.0,
              'incidence_angle': 37.5,
              'wavelength_mm': 56,  # with units of mm
              'plot_wrapped': True,                 # OPTIONAL PARAMETERS:
              'plot_unwrapped': True,
              'wrapped_plot_name': 'pred.jpg',
              'unwrapped_plot_name': 'unw_pred.jpg',
              'refidx': [0, 0],   # either [float, float] for lon, lat, or [int, int] for row, col
              'plot_range': None,
              'plot_wrapped_annot': None,
              'plot_unwrapped_annot': None,
              'outdir': '',
              'label': ''}

    # Combine dictionary with priority order using ** operator
    prio_dict = {1: params_provided, 2: defaults}
    params = {**prio_dict[2], **prio_dict[1]}
    return params;


def read_grd_inputs(params):
    """
    Reading an InSAR_2D_Object
    """
    myobj = InSAR_2D_Object.inputs.inputs_from_synthetic_enu_grids(params['east_grdfile'], params['north_grdfile'],
                                                                   params['up_grdfile'], params['flight_direction'],
                                                                   params['incidence_angle']);
    return myobj;


def plot_synthetic_grid_los(params, insarobj, disp_points=None, disp_points_color=None):
    """
    :param params: dictionary
    :param insarobj: a 2D InSAR object
    :param disp_points: a list of disp_points for optional plotting annotations
    :param disp_points_color: a 1d array of floats to be plotted as colors in the disp_points fill
    """
    if params['plot_unwrapped']:
        myobj_ref = InSAR_2D_Object.utilities.subtract_reference(insarobj, params['refidx']);  # Subtract reference pix
        InSAR_2D_Object.outputs.write_InSAR2D(myobj_ref, params['outdir'] + "/"+params['label']+"unw_phase.grd");
        InSAR_2D_Object.outputs.map_wrapped_insar(params['outdir']+"/"+params['label']+"unw_phase.grd",
                                                  params['outdir']+"/"+params['label']+params['unwrapped_plot_name'],
                                                  text_annot=params['plot_unwrapped_annot'],
                                                  flight_heading=params['flight_direction'],
                                                  disp_points=disp_points, region=params['plot_range'],
                                                  refloc=params['refidx'], disp_points_color=disp_points_color);

    if params['plot_wrapped']:
        myobj_wrapped = InSAR_2D_Object.utilities.rewrap_InSAR(insarobj, params['wavelength_mm']);
        InSAR_2D_Object.outputs.write_InSAR2D(myobj_wrapped, params['outdir']+"/"+params['label']+"phase.grd");
        InSAR_2D_Object.outputs.map_wrapped_insar(params['outdir']+"/"+params['label']+"phase.grd",
                                                  params['outdir']+"/"+params['label']+params["wrapped_plot_name"],
                                                  text_annot=params['plot_wrapped_annot'],
                                                  flight_heading=params['flight_direction'],
                                                  disp_points=disp_points, region=params['plot_range'], wrapped=True);
    return;


def do_synthetic_grid_LOS(params_provided, disp_points=None, disp_points_color=None):
    # SAMPLE DRIVER: CONFIG, INPUT, OUTPUT
    params = parse_config(params_provided);
    insarobj = read_grd_inputs(params);
    plot_synthetic_grid_los(params, insarobj, disp_points, disp_points_color);
    return;


if __name__ == "__main__":
    params_provided = parse_config({});  # could consider making this a command line application
    do_synthetic_grid_LOS(params_provided);