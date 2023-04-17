"""
Utilities on 1D InSAR_Obj
InSAR_1D_Object = ['lon','lat','LOS','LOS_unc','lkv_E','lkv_N','lkv_U','starttime','endtime']
LOS is in mm
"""

import numpy as np
from .class_model import InSAR_1D_Object
from Tectonic_Utils.geodesy import insar_vector_functions


def combine_objects(Obj1, Obj2):
    """
    Simply stack two objects, combining their pixels in the simplest way possible
    """
    lon = np.hstack((Obj1.lon, Obj2.lon));
    lat = np.hstack((Obj1.lat, Obj2.lat));
    LOS = np.hstack((Obj1.LOS, Obj2.LOS));
    LOS_unc = np.hstack((Obj1.LOS_unc, Obj2.LOS_unc));
    if LOS_unc.all() is None:
        LOS_unc = None;
    lkv_E = np.hstack((Obj1.lkv_E, Obj2.lkv_E));
    if lkv_E.all() is None:
        lkv_E = None;
    lkv_N = np.hstack((Obj1.lkv_N, Obj2.lkv_N));
    if lkv_N.all() is None:
        lkv_N = None;
    lkv_U = np.hstack((Obj1.lkv_U, Obj2.lkv_U));
    if lkv_U.all() is None:
        lkv_U = None;
    newInSAR_obj = InSAR_1D_Object(lon=lon, lat=lat, LOS=LOS, LOS_unc=LOS_unc, lkv_E=lkv_E, lkv_N=lkv_N, lkv_U=lkv_U,
                                   starttime=Obj1.starttime, endtime=Obj1.endtime);
    return newInSAR_obj;


def similar_pixel_tuples(tup1, tup2):
    tol = 1e-4;
    retval = 0;
    if np.abs(tup1[0] - tup2[0]) < tol:
        if np.abs(tup1[1] - tup2[1]) < tol:
            retval = 1;
    return retval;


def collect_common_pixels(Obj1, Obj2):
    """
    Take two InSAR objects (like Asc and Desc) and return two objects where the pixels are identical.
    Ignores pixels that have NaN in one dataset or the other
    Preparing for vector decomposition.
    """
    Obj1_tuples_list = [(Obj1.lon[x], Obj1.lat[x]) for x in range(len(Obj1.lon))];
    Obj2_tuples_list = [(Obj2.lon[x], Obj2.lat[x]) for x in range(len(Obj2.lon))];
    common_lon, common_lat = [], [];
    los1, los_unc1, lkv_e1, lkv_n1, lkv_u1 = [], [], [], [], [];
    los2, los_unc2, lkv_e2, lkv_n2, lkv_u2 = [], [], [], [], [];
    for i, pixel in enumerate(Obj1_tuples_list):
        find_idx = [similar_pixel_tuples(x, pixel) for x in Obj2_tuples_list];
        if np.sum(find_idx) == 0:
            continue;
        else:
            idx = find_idx.index(1);
            common_lon.append(pixel[0]);
            common_lat.append(pixel[1]);
            los1.append(Obj1.LOS[i]);
            los_unc1.append(Obj1.LOS_unc[i]);
            lkv_e1.append(Obj1.lkv_E[i]);
            lkv_n1.append(Obj1.lkv_N[i]);
            lkv_u1.append(Obj1.lkv_U[i]);
            los2.append(Obj2.LOS[idx]);
            los_unc2.append(Obj2.LOS_unc[idx]);
            lkv_e2.append(Obj2.lkv_E[idx]);
            lkv_n2.append(Obj2.lkv_N[idx]);
            lkv_u2.append(Obj2.lkv_U[idx]);

    common_Obj1 = InSAR_1D_Object(lon=common_lon, lat=common_lat, LOS=los1, LOS_unc=los_unc1, lkv_E=lkv_e1,
                                  lkv_N=lkv_n1, lkv_U=lkv_u1, starttime=Obj1.starttime, endtime=Obj1.endtime);
    common_Obj2 = InSAR_1D_Object(lon=common_lon, lat=common_lat, LOS=los2, LOS_unc=los_unc2, lkv_E=lkv_e2,
                                  lkv_N=lkv_n2, lkv_U=lkv_u2, starttime=Obj1.starttime, endtime=Obj1.endtime);

    return common_Obj1, common_Obj2;


def decompose_asc_desc_vert_horizontal(asc_obj, desc_obj):
    """
    Turn an ascending and descending object on the same pixels into vertical and horizontal.
    Appendix 1, Samieie-Esfahany et al., 2010
    The horiz is the horizontal projection into the azimuth of the descending look direction
    This function removes uncertainties rather than projecting them into vert/horiz.
    """
    vert, horz = [], [];
    for i in range(len(asc_obj.LOS)):
        [flight_asc, inc_asc] = insar_vector_functions.look_vector2flight_incidence_angles(asc_obj.lkv_E[i],
                                                                                           asc_obj.lkv_N[i],
                                                                                           asc_obj.lkv_U[i]);
        [flight_desc, inc_desc] = insar_vector_functions.look_vector2flight_incidence_angles(desc_obj.lkv_E[i],
                                                                                             desc_obj.lkv_N[i],
                                                                                             desc_obj.lkv_U[i]);
        obs_vector = np.array([asc_obj.LOS[i], desc_obj.LOS[i]]);
        cos_theta_asc = np.cos(np.deg2rad(inc_asc));
        sin_theta_asc = np.sin(np.deg2rad(inc_asc));
        cos_theta_desc = np.cos(np.deg2rad(inc_desc));
        sin_theta_desc = np.sin(np.deg2rad(inc_desc));
        x = 1/np.cos(np.deg2rad(flight_asc - flight_desc));   # the azimuth difference between asc and desc headings
        A_forward = np.array([[cos_theta_asc, sin_theta_asc*x], [cos_theta_desc, sin_theta_desc]]);
        A_inverse = np.linalg.inv(A_forward);
        retvec = np.dot(A_inverse, obs_vector);
        vert.append(retvec[0]);
        horz.append(retvec[1]);

    Vert_obj = InSAR_1D_Object(lon=asc_obj.lon, lat=asc_obj.lat, LOS=vert, LOS_unc=np.zeros(np.shape(vert)),
                               lkv_E=np.zeros(np.shape(vert)),
                               lkv_N=np.zeros(np.shape(vert)),
                               lkv_U=np.ones(np.shape(vert)), starttime=asc_obj.starttime, endtime=asc_obj.endtime);
    Horz_obj = InSAR_1D_Object(lon=asc_obj.lon, lat=asc_obj.lat, LOS=horz, LOS_unc=np.zeros(np.shape(vert)),
                               lkv_E=np.zeros(np.shape(vert)),
                               lkv_N=np.zeros(np.shape(vert)),
                               lkv_U=np.zeros(np.shape(vert)), starttime=asc_obj.starttime, endtime=asc_obj.endtime);
    return Vert_obj, Horz_obj;


def proj_los_into_vertical_no_horiz(InSAR_obj, const_lkv=None):
    """
    Project LOS deformation into psudo-vertical, assuming no horizontal motion.
    The look vector can be a constant approximation applied to all pixels, or it can be derived from
    pixel-by-pixel look vectors.
    """
    new_los = [];
    for i in range(len(InSAR_obj.lon)):
        if const_lkv is None:
            specific_lkv = [InSAR_obj.lkv_E[i], InSAR_obj.lkv_N[i], InSAR_obj.lkv_U[i]];
            new_los.append(insar_vector_functions.proj_los_into_vertical_no_horiz(InSAR_obj.LOS[i], specific_lkv));
        else:
            new_los.append(insar_vector_functions.proj_los_into_vertical_no_horiz(InSAR_obj.LOS[i], const_lkv));
    newInSAR_obj = InSAR_1D_Object(lon=InSAR_obj.lon, lat=InSAR_obj.lat, LOS=new_los, LOS_unc=InSAR_obj.LOS_unc,
                                   lkv_E=np.zeros(np.shape(InSAR_obj.lon)), lkv_N=np.zeros(np.shape(InSAR_obj.lon)),
                                   lkv_U=np.ones(np.shape(InSAR_obj.lon)),
                                   starttime=InSAR_obj.starttime, endtime=InSAR_obj.endtime);
    return newInSAR_obj;
