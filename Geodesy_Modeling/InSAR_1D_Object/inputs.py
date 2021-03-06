# August 12, 2020
# Definition of InSAR-format data
# Input functions for InSAR-format data


import numpy as np
import datetime as dt
import sys
import pandas
import h5py
from read_write_insar_utilities import isce_read_write
from Tectonic_Utils.geodesy import insar_vector_functions
from .class_model import InSAR_1D_Object


def inputs_txt(insar_textfile):
    """Input function for invertible text file"""
    [lon_meas, lat_meas, disp, sig, unit_e, unit_n, unit_u] = np.loadtxt(insar_textfile, unpack=True, skiprows=1);
    InSAR_Obj = InSAR_1D_Object(lon=lon_meas, lat=lat_meas, LOS=disp*1000, LOS_unc=sig*1000, lkv_E=unit_e, lkv_N=unit_n,
                                lkv_U=unit_u, starttime=dt.datetime.strptime("19900101", "%Y%m%d"),
                                endtime=dt.datetime.strptime("19900101", "%Y%m%d"));
    return InSAR_Obj;


def inputs_simplest_txt(insar_textfile):
    """Input function for lon, lat, LOS (mm)"""
    [lon_meas, lat_meas, disp] = np.loadtxt(insar_textfile, unpack=True, skiprows=1);
    InSAR_Obj = InSAR_1D_Object(lon=lon_meas, lat=lat_meas, LOS=disp, LOS_unc=None, lkv_E=None, lkv_N=None,
                                lkv_U=None, starttime=None, endtime=None);
    return InSAR_Obj;


def inputs_TRE_vert_east(filename):
    """
    Reading InSAR data from TRE data in excel spreadsheets.
    """
    print("Reading in %s" % filename);

    # Vertical velocities
    vert_sheet = pandas.read_excel(filename, engine='openpyxl', sheet_name=2);
    zvel = vert_sheet['VEL'].values.tolist();
    zvel_std = vert_sheet['VEL_STD'].values.tolist();
    lat = vert_sheet['LAT'].values.tolist();
    lon = vert_sheet['LON'].values.tolist();

    # East velocities
    east_sheet = pandas.read_excel(filename, engine='openpyxl', sheet_name=3);
    evel = east_sheet['VEL'].values.tolist();
    evel_std = east_sheet['VEL_STD'].values.tolist();

    if "TSX" in filename:
        starttime = dt.datetime.strptime("2012-09-01", "%Y-%m-%d");
        endtime = dt.datetime.strptime("2013-09-01", "%Y-%m-%d");  # Hard coded for this experiment.
    elif "SNT1" in filename:
        starttime = dt.datetime.strptime("2015-04-01", "%Y-%m-%d");
        endtime = dt.datetime.strptime("2018-04-01", "%Y-%m-%d");  # Hard coded for this experiment.
    elif "SNT2" in filename:
        starttime = dt.datetime.strptime("2018-05-01", "%Y-%m-%d");
        endtime = dt.datetime.strptime("2019-08-01", "%Y-%m-%d");  # Hard coded for this experiment.
    elif "ENV_2005" in filename:
        starttime = dt.datetime.strptime("2005-08-01", "%Y-%m-%d");  # for Heber experiment, vertical/east
        endtime = dt.datetime.strptime("2010-08-01", "%Y-%m-%d");  # for Heber experiment, vertical/east
        # Heber dataset:
        # ascending: 12-2003 to 08-2010 (but denser data starts at 08-2005)
        # descending: 02-2003 to 09-2010
        # vertical/east : 08-2005 to 08-2010
    else:
        print("Unrecognized TRE filename option! Cannot find start and end times.  Exiting...");
        sys.exit(0);

    # Packaging it up
    # Divide by the number of years of observation
    # Return the Vert and East as separate objects
    Vert_LOS = convert_rates_to_disps(zvel, starttime, endtime);
    East_LOS = convert_rates_to_disps(evel, starttime, endtime);
    zeros = np.zeros(np.shape(zvel));
    ones = np.ones(np.shape(zvel));
    Vert_obj = InSAR_1D_Object(lon=lon, lat=lat, LOS=Vert_LOS, LOS_unc=zvel_std,
                               lkv_E=zeros, lkv_N=zeros, lkv_U=ones, starttime=starttime, endtime=endtime);
    East_obj = InSAR_1D_Object(lon=lon, lat=lat, LOS=East_LOS, LOS_unc=evel_std,
                               lkv_E=ones, lkv_N=zeros, lkv_U=zeros, starttime=starttime, endtime=endtime);

    return Vert_obj, East_obj;


# INPUT FUNCTION FOR CONTRIBUTED S1 DATASET
def inputs_cornell_ou_velocities_hdf5(filename, lkv_filename, slicenum=0):
    """
    This is for one track at a time.
    In this case, the hdf5 file contains 5 velocity measurements for each pixel, one at each time interval.
    We will return whichever slicenum (0-4) is supplied
    """
    print("Reading %s " % filename);
    f = h5py.File(filename, 'r');  # reads the hdf5 into a dictionary f

    # Unpacking
    dates = np.array(f.get('dates'));
    print(dates);
    lat = np.array(f.get('lat'));
    lon = np.array(f.get('lon'));
    rate = np.array(f.get('rate'));
    rstd = np.array(f.get('rstd'));

    f2 = h5py.File(lkv_filename, 'r');
    los = f2.get('los')
    lkv_E = los[0, :, :]
    lkv_N = los[1, :, :]
    lkv_U = los[2, :, :]

    num_data = np.shape(lon)[0] * np.shape(lon)[1];
    lon = np.reshape(lon, (num_data,));
    lat = np.reshape(lat, (num_data,));
    lkv_E = np.reshape(lkv_E, (num_data,));
    lkv_N = np.reshape(lkv_N, (num_data,));
    lkv_U = np.reshape(lkv_U, (num_data,));
    unc = np.reshape(rstd[:, :, slicenum], (num_data,));
    disps, dates = quick_convert_one_timeslice_to_disp(rate[:, :, slicenum], dates[slicenum]);

    # Returning the standard InSAR format of displacements in mm, etc.
    InSAR_data = InSAR_1D_Object(lon=lon, lat=lat, LOS=disps, LOS_unc=unc, lkv_E=lkv_E, lkv_N=lkv_N, lkv_U=lkv_U,
                                 starttime=dates[0], endtime=dates[1]);
    return InSAR_data;


def inputs_isce_unw_geo_losrdr(isce_unw_filename, los_filename, time_bounds=(None, None)):
    """
    Function to read a geocoded unw file and associated rdr.los.geo, and
    extract an InSAR object.
    In the return value, each field is a vector.
    """
    xarray, yarray, data = isce_read_write.read_isce_unw_geo(isce_unw_filename);
    incidence = isce_read_write.read_scalar_data(los_filename, band=1);
    azimuth = isce_read_write.read_scalar_data(los_filename, band=2);
    lkv_e, lkv_n, lkv_u = insar_vector_functions.calc_lkv_from_rdr_azimuth_incidence(azimuth, incidence);

    [X, Y] = np.meshgrid(xarray, yarray);
    num_data = np.shape(data)[0] * np.shape(data)[1];
    lon = np.reshape(X, (num_data,));
    lat = np.reshape(Y, (num_data,));
    data = np.reshape(data, (num_data,));
    lkv_e = np.reshape(lkv_e, (num_data,));
    lkv_n = np.reshape(lkv_n, (num_data,));
    lkv_u = np.reshape(lkv_u, (num_data,));
    InSAR_data = InSAR_1D_Object(lon=lon, lat=lat, LOS=data, LOS_unc=np.zeros(np.shape(data)), lkv_E=lkv_e,
                                 lkv_N=lkv_n, lkv_U=lkv_u, starttime=time_bounds[0], endtime=time_bounds[1]);
    return InSAR_data;


def quick_convert_one_timeslice_to_disp(rateslice, date_intformat):
    """A function that does displacement = rate x time"""
    numdata = np.shape(rateslice)[0] * np.shape(rateslice)[1];
    ratevector = np.reshape(rateslice, (numdata,));
    datevector = [dt.datetime.strptime(str(date_intformat[0]), "%Y%m%d"),
                  dt.datetime.strptime(str(date_intformat[1]), "%Y%m%d")];
    disps = convert_rates_to_disps(ratevector, datevector[0], datevector[1]);
    return disps, datevector;


def convert_rates_to_disps(LOS_rates, starttime, endtime):
    """LOS_rates is a vector. starttime/endtime are datetime objects"""
    tdelta = endtime - starttime;
    interval_years = tdelta.days / 365.24;  # the number of years spanned by the velocity.
    Disps = [i * interval_years for i in LOS_rates];
    return Disps;
