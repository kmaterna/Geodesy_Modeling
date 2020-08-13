# August 12, 2020
# Definition of InSAR-format data
# Input functions for InSAR-format data


import numpy as np 
import datetime as dt 
import xlrd
import h5py
from .class_model import InSAR_Object

# INPUT FUNCTION FOR REGULAR TEXT FILE: 
def inputs_txt(insar_textfile):
	[lon_meas, lat_meas, disp, sig, unit_e, unit_n, unit_u] = np.loadtxt(insar_textfile, unpack=True, skiprows=1);
	InSAR_Obj = InSAR_Object(lon=lon_meas, lat=lat_meas, LOS=disp, LOS_unc=sig, lkv_E=unit_e, lkv_N=unit_n, lkv_U=unit_u, starttime=None, endtime=None);
	return InSAR_Obj;


# INPUT FUNCTION FOR TRE-DERIVED S1 AND TSX
def inputs_TRE(filename):
	# Reading data from SNT1 TRE data. 
	print("Reading in %s" % filename);
	wb = xlrd.open_workbook(filename);

	# Vertical velocities
	sheet = wb.sheet_by_index(2);
	numcols = sheet.ncols;
	numrows = sheet.nrows; 
	data = [[sheet.cell_value(r,c) for c in range(numcols)] for r in range(numrows)];
	length, width = np.shape(data);
	zvel = [data[i][0] for i in range(1,length)];
	zvel_std = [data[i][1] for i in range(1,length)];
	lat = [data[i][2] for i in range(1,length)];
	lon = [data[i][3] for i in range(1,length)];

	# East velocities
	sheet = wb.sheet_by_index(3);
	numcols = sheet.ncols;
	numrows = sheet.nrows; 
	data = [[sheet.cell_value(r,c) for c in range(numcols)] for r in range(numrows)];
	length, width = np.shape(data);
	evel = [data[i][0] for i in range(1,length)];
	evel_std = [data[i][1] for i in range(1,length)];

	if "TSX" in filename:
		starttime=dt.datetime.strptime("2012-09-01","%Y-%m-%d");
		endtime=dt.datetime.strptime("2013-09-01","%Y-%m-%d");  # Hard coded for this experiment. 
	if "SNT1" in filename:
		starttime=dt.datetime.strptime("2014-04-01","%Y-%m-%d");
		endtime=dt.datetime.strptime("2018-04-01","%Y-%m-%d");  # Hard coded for this experiment. 
	if "SNT2" in filename:
		starttime=dt.datetime.strptime("2018-05-01","%Y-%m-%d");
		endtime=dt.datetime.strptime("2019-08-01","%Y-%m-%d");  # Hard coded for this experiment. 

	# Packaging it up
	# Divide by the number of years of observation
	# Return the Vert and East as separate objects
	Vert_LOS = convert_rates_to_disps(zvel, starttime, endtime);
	East_LOS = convert_rates_to_disps(evel, starttime, endtime);
	zeros = np.zeros(np.shape(zvel));
	ones = np.ones(np.shape(zvel));
	Vert_obj = InSAR_Object(lon=lon, lat=lat, LOS=Vert_LOS, LOS_unc=zvel_std, 
		lkv_E=zeros, lkv_N=zeros, lkv_U=ones, starttime=starttime, endtime=endtime);
	East_obj = InSAR_Object(lon=lon, lat=lat, LOS=East_LOS, LOS_unc=evel_std, 
		lkv_E=ones, lkv_N=zeros, lkv_U=zeros, starttime=starttime, endtime=endtime);
	
	return Vert_obj, East_obj;



# INPUT FUNCTION FOR CONTRIBUTED S1 DATASET
def inputs_cornell_ou_velocities_hdf5(filename, slicenum=0):
	# This is for one track at a time.  
	# In this case, the hdf5 file contains 5 velocity measurements for each pixel, one at each time interval. 
	# We will return whichever slicenum (0-4) is supplied
	f = h5py.File(filename,'r');  # reads the hdf5 into a dictionary f

	# Unpacking
	dates = np.array(f.get('dates'));
	lat = np.array(f.get('lat'));
	lon = np.array(f.get('lon'));
	rate = np.array(f.get('rate'));
	rstd = np.array(f.get('rstd'));

	num_data = np.shape(lon)[0]*np.shape(lon)[1];
	lon=np.reshape(lon, (num_data,));
	lat=np.reshape(lat, (num_data,));
	disps, dates = quick_convert_one_timeslice_to_disp(rate[:,:,slicenum],dates[slicenum]);

	# Returning the standard InSAR format of displacements in mm, etc. 
	InSAR_data = InSAR_Object(lon=lon, lat=lat, LOS=disps, LOS_unc=None, lkv_E=None, lkv_N=None, lkv_U=None, starttime=dates[0], endtime=dates[1]);
	return InSAR_data;

def quick_convert_one_timeslice_to_disp(rateslice, date_intformat):
	numdata = np.shape(rateslice)[0]*np.shape(rateslice)[1];
	ratevector = np.reshape(rateslice, (numdata,));
	datevector = [dt.datetime.strptime(str(date_intformat[0]),"%Y%m%d"), dt.datetime.strptime(str(date_intformat[1]),"%Y%m%d")];
	disps = convert_rates_to_disps(ratevector, datevector[0], datevector[1]);
	return disps, datevector; 

def convert_rates_to_disps(LOS_rates, starttime, endtime):
	# LOS_rates is a vector. starttime/endtime are datetime objects
	tdelta = endtime-starttime;
	interval_years = tdelta.days / 365.24;  # the number of years spanned by the velocity. 	
	Disps = [i*interval_years for i in LOS_rates];
	return Disps; 


