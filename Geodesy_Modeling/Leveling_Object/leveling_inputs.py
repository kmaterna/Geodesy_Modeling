# A series of functions for io of leveling data
# LEVELING INPUT FUNCTIONS FOR CEC SALTON TROUGH LEVELING DATA

import collections
import datetime as dt
import numpy as np
import xlrd
from matplotlib import pyplot as plt

LevData = collections.namedtuple("LevData", ["name", "lat", "lon", "dtarray", "leveling"]);


def inputs_leveling(data_filename, errors_filename):
    """Read leveling from CEC Salton Trough leveling data"""

    print("Reading in %s" % data_filename);
    wb = xlrd.open_workbook(data_filename);
    sheet = wb.sheet_by_index(0);
    numcols = sheet.ncols;
    numrows = sheet.nrows;
    data = [[sheet.cell_value(r, c) for c in range(numcols)] for r in range(numrows)];
    [rownum, colnum, old_values, new_values] = read_errors(errors_filename);
    data = implement_changes(data, rownum, colnum, old_values, new_values);

    dtarray = get_datetimes(data[0][1:-1]);
    names = [data[i][0] for i in range(1, numrows)];

    # # Get the latitude and longitude information
    latsheet = wb.sheet_by_index(2);
    latitudes = latsheet.col_values(1)[1:];
    longitudes = latsheet.col_values(2)[1:];
    ll_names = latsheet.col_values(0)[1:];
    names, lons, lats = match_lon_lat(names, latitudes, longitudes, ll_names);

    leveling_array = [];
    for i in range(1, numrows):
        single_leveling_array = data[i][1:13];
        single_leveling_array = clean_single_ts(single_leveling_array);
        leveling_array.append(single_leveling_array);

    myLev = LevData(name=names, lon=lons, lat=lats, dtarray=dtarray, leveling=leveling_array);
    return myLev;


def read_errors(filename):
    print("Reading documented errors in %s " % filename)
    rownum = [];
    colnum = [];
    old_values = [];
    new_values = [];
    ifile = open(filename, 'r');
    for line in ifile:
        temp = line.split("::");
        if temp[0] == "Row":
            continue;
        rownum.append(int(temp[0]));
        colnum.append(int(temp[1]));
        old_values.append(temp[2]);
        new_values.append(temp[3]);
    ifile.close();
    return [rownum, colnum, old_values, new_values];


def implement_changes(data, rownum, colnum, old_values, new_values):
    print("Implementing changes to data:");
    for i in range(len(rownum)):
        # Catching any bugs and errors
        if str(data[rownum[i]][colnum[i]]) != str(old_values[i]):
            print("PROBLEM at row %d! Attempting to modify data. Value found %s does not match expected value %s "
                  % (i, data[rownum[i]][colnum[i]], old_values[i]));
            print("Skipping.");
            continue;

        else:
            # Over-writing the data
            print("MODIFYING data at %d, %d: %s goes to %s" % (rownum[i], colnum[i], old_values[i], new_values[i]));
            if type(data[rownum[i]][colnum[i]]) == str:
                data[rownum[i]][colnum[i]] = new_values[i];
            elif type(data[rownum[i]][colnum[i]]) == float:
                data[rownum[i]][colnum[i]] = float(new_values[i]);
            elif type(data[rownum[i]][colnum[i]]) == int:
                data[rownum[i]][colnum[i]] = int(new_values[i]);
    return data;


def get_datetimes(timestrings):
    dtarray = [];
    for i in range(len(timestrings)):
        # Normal dates
        if " 88 " in timestrings[i]:
            temp = timestrings[i].split(" 88 ");
            temp2 = temp[1].split();
            mmm = temp2[0];
            year = temp2[1];
            dtarray.append(dt.datetime.strptime(year + "-" + mmm + "-01",
                                                "%Y-%b-%d"));  # issue here, but not too bad.
        else:  # For the special cases
            if "NOLTE 2008" in timestrings[i]:
                dtarray.append(dt.datetime.strptime("2008-Nov-01", "%Y-%b-%d"));
    return dtarray;


def match_lon_lat(names, lats, lons, ll_names):
    """Pair up the latlon info with the timeseries info"""
    matched_lons = [];
    matched_lats = [];
    for i in range(len(names)):
        find_name = names[i];
        if names[i] == "Y-1225 Datum":
            find_name = "Y 1225";
        idx = ll_names.index(find_name);
        matched_lats.append(lats[idx]);
        matched_lons.append(lons[idx]);
    return [names, matched_lons, matched_lats];


def clean_single_ts(array):
    newarray = [];
    for i in range(len(array)):
        if str(array[i]) == "-" or str(array[i]) == "DESTROYED" or str(array[i]) == "DAMAGED" or str(
                array[i]) == "NOT" or str(array[i]) == "FOUND":
            newarray.append(np.nan);
        else:
            newarray.append(array[i]);
    return newarray;


# LEVELING COMPUTE FUNCITON (REFERENCE TO DATUM)
def compute_rel_to_datum_nov_2009(data):
    """Skips the 2008 measurement. Returns an object that is 83x10"""
    arrays_of_ref_leveling = [];
    for i in range(len(data.name)):

        # Automatically find the first day that matters.  Either after 2008 or has data.
        for j in range(len(data.dtarray)):
            if ~np.isnan(data.leveling[i][j]) and data.dtarray[j] > dt.datetime.strptime("2009-01-01", "%Y-%m-%d"):
                idx = j;  # this is the first date after 2009 that has data
                break;

        # Accounting for a change in Datum height in 2014
        idx_early = 6;  # the placement of 2014 before adjustment on the spreadsheet
        idx_late = 7;  # the placement of 2014 after adjustment on the spreadsheet
        step = data.leveling[i][idx_early] - data.leveling[i][idx_late];

        referenced_dates, referenced_data = [], [];

        for j in range(1, len(data.dtarray)):  # skipping 2008 anyway.
            if j == 6:
                continue;  # passing over the 2014 measurement before re-referencing.
            if data.dtarray[j] > dt.datetime.strptime("2014-01-01", "%Y-%m-%d"):
                referenced_dates.append(data.dtarray[j]);
                referenced_data.append(data.leveling[i][j] - data.leveling[i][idx] + step);
            else:
                referenced_dates.append(data.dtarray[j]);
                referenced_data.append(data.leveling[i][j] - data.leveling[i][idx]);

        arrays_of_ref_leveling.append(referenced_data);
    referenced_object = LevData(name=data.name, lon=data.lon, lat=data.lat, dtarray=referenced_dates,
                                leveling=arrays_of_ref_leveling);
    return referenced_object;


# -------------- WRITE FUNCTIONS ------------- #

def write_leveling_invertible_format(myLev, idx1, idx2, unc, filename):
    """One header line
    One datum line (automatically first in the leveling array anyway)
    Lon, lat, disp, sigma, 0, 0, 1 (in m)"""
    print("Writing leveling to file %s " % filename);
    ofile = open(filename, 'w');
    ofile.write("# Displacement for %s to %s: Lon, Lat, disp(m), sigma, 0, 0, 1 \n" %
                (dt.datetime.strftime(myLev.dtarray[idx1], "%Y-%m-%d"),
                 dt.datetime.strftime(myLev.dtarray[idx2], "%Y-%m-%d")))
    for i in range(len(myLev.leveling)):
        data = myLev.leveling[i][idx2] - myLev.leveling[i][idx1];
        if ~np.isnan(data):
            ofile.write("%f %f %f %f 0 0 1\n" % (myLev.lon[i], myLev.lat[i], data, unc))
    ofile.close();
    return;


def plot_leveling(txtfile, plotname):
    print("Plotting leveling in file %s " % plotname);
    [lon, lat, disp] = np.loadtxt(txtfile, unpack=True, skiprows=1, usecols=(0, 1, 2));
    plt.figure(dpi=300);
    plt.scatter(lon, lat, c=disp, s=40, cmap='rainbow')
    plt.colorbar();
    plt.savefig(plotname);
    return;