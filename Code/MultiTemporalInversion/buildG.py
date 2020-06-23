
import numpy as np 
import matplotlib.pyplot as plt 
import slippy.xyz2geo as plotting_library
import slippy.basis
import slippy.patch
import slippy.tikhonov
import slippy.gbuild
import scipy.optimize
import scipy.linalg
import slippy.io

def reg_nnls(Gext,dext):
  return scipy.optimize.nnls(Gext,dext)[0]

def G_with_smoothing(G,L,alpha, d):
  # Add smoothing and other regularization
  # Expand the data to match. 
  dext = np.concatenate((d,np.zeros(L.shape[0])))
  Gext = np.vstack((G,L))
  if alpha > 0:  # Minimum norm solution. Aster and Thurber, Equation 4.5.
    alphaI = alpha * np.identity(np.shape(Gext)[1])
    alphaI[-1,-1] = 0;  # for leveling, we don't want the offset term to be constrained. 
    zero_vector = np.zeros( (np.shape(Gext)[1],) )
    Gext = np.vstack((Gext, alphaI))
    dext = np.concatenate( (dext, zero_vector) )	
  return Gext, dext;


def input_gps_file(filename):

  obs_disp_f = np.zeros((0,))
  obs_sigma_f = np.zeros((0,))
  obs_pos_geo_f = np.zeros((0,3))  
  obs_basis_f = np.zeros((0,3))

  gps_input = slippy.io.read_gps_data(filename);
  Ngps = len(gps_input[0])
  Nleveling = 0  # change this if we're reading leveling 
  leveling_sign = 1;
  obs_gps_pos_geo = gps_input[0]
  obs_gps_disp = gps_input[1]
  obs_gps_sigma = gps_input[2]
  obs_gps_basis = slippy.basis.cardinal_basis((Ngps,3))
    
  obs_disp_fi = obs_gps_disp.reshape((Ngps*3,))
  obs_sigma_fi = obs_gps_sigma.reshape((Ngps*3,))
  obs_basis_fi = obs_gps_basis.reshape((Ngps*3,3))
  obs_pos_geo_fi = obs_gps_pos_geo[:,None,:].repeat(3,axis=1).reshape((Ngps*3,3))
    
  obs_disp_f = np.concatenate((obs_disp_f,obs_disp_fi),axis=0)
  obs_sigma_f = np.concatenate((obs_sigma_f,obs_sigma_fi),axis=0)
  obs_basis_f = np.concatenate((obs_basis_f,obs_basis_fi),axis=0)    
  obs_pos_geo_f = np.concatenate((obs_pos_geo_f,obs_pos_geo_fi),axis=0)

  print("Reading %d gps data from %s " % ( len(gps_input[0]),filename) ) ; 

  return [obs_disp_f, obs_sigma_f, obs_basis_f, obs_pos_geo_f, Ngps, Nleveling, leveling_sign];

def input_insar_file(filename):
  
  obs_disp_f = np.zeros((0,))
  obs_sigma_f = np.zeros((0,))
  obs_pos_geo_f = np.zeros((0,3))  
  obs_basis_f = np.zeros((0,3))

  insar_input = slippy.io.read_insar_data(filename)    
  Ninsar = len(insar_input[0])
  Nleveling = 0  # change this if we're reading leveling 
  leveling_sign = 1;
  obs_insar_pos_geo = insar_input[0]
  obs_insar_disp = insar_input[1]
  obs_insar_sigma = insar_input[2]
  obs_insar_basis = insar_input[3]

  obs_disp_f = np.concatenate((obs_disp_f,obs_insar_disp),axis=0)
  obs_sigma_f = np.concatenate((obs_sigma_f,obs_insar_sigma),axis=0)
  obs_basis_f = np.concatenate((obs_basis_f,obs_insar_basis),axis=0)    
  obs_pos_geo_f = np.concatenate((obs_pos_geo_f,obs_insar_pos_geo),axis=0)
  
  print("Reading %d insar data from %s " % ( len(insar_input[0]),filename) ) ; 

  return [obs_disp_f, obs_sigma_f, obs_basis_f, obs_pos_geo_f, Ninsar, Nleveling, leveling_sign]; 


def beginning_calc(config):

  # Read Faults into a list of faults (each fault being a dict)
  fault_list = [];
  for key in config["faults"].keys():
    basis = []
    for b in ['basis1','basis2','basis3']:
      basis_i = config["faults"][key].pop(b,None)
      if basis_i is None:
        continue
      basis += [basis_i]  	
    fault_segment = {
      "strike":config["faults"][key]["strike"],
      "dip":config["faults"][key]["dip"],
      "length":config["faults"][key]["length"],
      "width":config["faults"][key]["width"],
      "seg_pos_geo":config["faults"][key]["position"],
      "Nlength":config["faults"][key]["Nlength"],
      "Nwidth":config["faults"][key]["Nwidth"],
      "penalty":config["faults"][key]["penalty"],
      "slip_basis":basis};
    fault_list.append(fault_segment)
    alpha = config['alpha']


  # Setting up the basemap before we begin (using the GPS as information)
  for interval in config["gps_data"].keys():
    gps_input = slippy.io.read_gps_data(config["prep_inputs_dir"]+config["gps_data"][interval]["gps_textfile"]);
    Ngps = len(gps_input[0])
    obs_gps_pos_geo = gps_input[0]
    obs_pos_geo_basemap = obs_gps_pos_geo[:,None,:].repeat(3,axis=1).reshape((Ngps*3,3))
  bm = plotting_library.create_default_basemap(obs_pos_geo_basemap[:,0],obs_pos_geo_basemap[:,1]) 


  # # ###################################################################
  # ### discretize the fault segments
  # ### create slip basis vectors for each patch  
  # ### build regularization matrix
  # ###################################################################
  patches = [];  # a growing list of fault patches. 
  slip_basis_f = np.zeros((0,3)) # a growing list of basis functions for slip patches
  total_fault_slip_basis=[];
  patches_f = [];
  L_array = [];
  Ns_total=0;
  
  # # Fault processing
  for fault in fault_list:  
    # Convert fault to cartesian coordinates  
    fault["seg_pos_cart"] = plotting_library.geodetic_to_cartesian(fault["seg_pos_geo"],bm)

    # Discretize fault segment
    seg = slippy.patch.Patch(fault["seg_pos_cart"],
                             fault["length"],fault["width"],
                             fault["strike"],fault["dip"])
    single_fault_patches = np.array(seg.discretize(fault["Nlength"],fault["Nwidth"]))
    Ns = len(single_fault_patches);

    # Create slip basis vectors
    Ds = len(fault["slip_basis"])  # the number of basis vectors for this slip patch. 
    single_fault_slip_basis = np.array([fault["slip_basis"] for j in range(Ns)])  
    if total_fault_slip_basis==[]:
      total_fault_slip_basis = single_fault_slip_basis;
    else:
      total_fault_slip_basis=np.concatenate((total_fault_slip_basis, single_fault_slip_basis),axis=0)
    single_fault_silp_basis_f = single_fault_slip_basis.reshape((Ns*Ds,3))

    # Packaging of slip_basis_f
    single_fault_patches_f = single_fault_patches[:,None].repeat(Ds,axis=1).reshape((Ns*Ds,))
    patches=np.concatenate((patches,single_fault_patches),axis=0)
    patches_f=np.concatenate((patches_f,single_fault_patches_f),axis=0)
    slip_basis_f=np.concatenate((slip_basis_f, single_fault_silp_basis_f),axis=0);

    ### build regularization matrix
    L = np.zeros((0,Ns*Ds))
    indices = np.arange(Ns*Ds).reshape((Ns,Ds))
    for i in range(Ds): 
      connectivity = indices[:,i].reshape((fault["Nlength"],fault["Nwidth"]))
      Li = slippy.tikhonov.tikhonov_matrix(connectivity,2,column_no=Ns*Ds)
      L = np.vstack((Li,L))

    L *= fault["penalty"] 
    L_array.append(L)
    Ns_total = Ns_total+Ns
  L_array.append([0]);  # for the leveling offset parameter we will be solving for. 
  L = scipy.linalg.block_diag(*L_array)  # Make the block diagonal matrix for tikhonov regularization


  # PARSE HOW MANY EPOCHS WE ARE USING
  # This will tell us how many epochs, model parameters total, and output files we need. 
  n_epochs = 0;
  total_spans = [];
  span_output_files = [];  
  for epoch in config["epochs"].keys():
    n_epochs = n_epochs+1;
    total_spans.append(config["epochs"][epoch]["name"]);
    span_output_files.append(config["output_dir"]+"span_"+config["epochs"][epoch]["name"]+"_slip.txt");
  n_model_params = np.shape(L)[0];  
  print("Finding fault model for %d epochs " % n_epochs);
  print("Number of model parameters per epoch: %d" % n_model_params );

  # INITIALIZING THE LARGE MATRICIES
  d_total = np.zeros((0,));
  sig_total = np.zeros((0,));
  G_total = np.zeros((0,n_epochs*n_model_params));
  G_nosmooth_total = np.zeros((0,n_epochs*n_model_params));
  nums_obs = [];
  pos_obs_list = []; 
  pos_basis_list = [];

  # INITIAL DATA SCOPING: HOW MANY FILES WILL NEED TO BE READ?
  input_file_list = []; 
  spans_list = [];
  data_type_list = [];
  print("Available data indicated in json file: ")
  if "gps_data" in config.keys():
    for interval in config["gps_data"].keys():
      gps_file = config["prep_inputs_dir"]+config["gps_data"][interval]["gps_textfile"];
      this_data_spans = config["gps_data"][interval]["span"];
      print(gps_file," spans ",this_data_spans);
      input_file_list.append(gps_file);
      spans_list.append(this_data_spans);
      data_type_list.append('gps');

  if "uavsar_data" in config.keys():
    for interval in config["uavsar_data"].keys():
      uavsar_file = config["prep_inputs_dir"]+config["uavsar_data"][interval]["uav_textfile"];
      this_data_spans = config["uavsar_data"][interval]["span"];
      print(uavsar_file," spans ",this_data_spans);
      input_file_list.append(uavsar_file);
      spans_list.append(this_data_spans);
      data_type_list.append('uavsar'); 

  if "leveling_data" in config.keys():
    for interval in config["leveling_data"].keys():
      lev_file = config["prep_inputs_dir"]+config["leveling_data"][interval]["lev_outfile"];
      this_data_spans = config["leveling_data"][interval]["span"];
      print(lev_file," spans ",this_data_spans);
      input_file_list.append(lev_file);
      spans_list.append(this_data_spans);
      data_type_list.append('leveling');

  if "tsx_data" in config.keys():
    for interval in config["tsx_data"].keys():
      tsx_file = config["prep_inputs_dir"]+config["tsx_data"][interval]["tsx_datafile"];
      this_data_spans = config["tsx_data"][interval]["span"];
      print(tsx_file," spans ",this_data_spans);
      input_file_list.append(tsx_file);
      spans_list.append(this_data_spans);
      data_type_list.append('tsx');



  # START THE MAJOR INVERSION LOOP
  for filenum in range(len(input_file_list)):

  	# INPUT STAGE
    filename = input_file_list[filenum];
    if data_type_list[filenum]=='gps':
      [obs_disp_f, obs_sigma_f, obs_basis_f, obs_pos_geo_f, Ngps, Nleveling, leveling_sign] = input_gps_file(filename);
    elif data_type_list[filenum]=='uavsar':
      [obs_disp_f, obs_sigma_f, obs_basis_f, obs_pos_geo_f, Ngps, Nleveling, leveling_sign] = input_insar_file(filename);
    elif data_type_list[filenum]=="leveling" or data_type_list[filenum]=='tsx':
      [obs_disp_f, obs_sigma_f, obs_basis_f, obs_pos_geo_f, Ninsar, Nleveling, leveling_sign] = input_insar_file(filename);
      if 'B' in filename:
        leveling_sign=-1*leveling_sign;  # feel free to adjust the non-negative inversion parameter here. 
      Nleveling = Ninsar; 
    else:
      print("ERROR! Unrecognized data type %s " % data_type_list[filenum]);
      continue;
    
    # Metadata collection about this input source
    pos_obs_list.append(obs_pos_geo_f);  # for writing the outputs later
    nums_obs.append(len(obs_disp_f));
    pos_basis_list.append(obs_basis_f);
    this_data_spans = spans_list[filenum];
    print("This data spans:", this_data_spans);       

    # # Geodetic to Cartesian coordinates
    obs_pos_cart_f = plotting_library.geodetic_to_cartesian(obs_pos_geo_f,bm)  

    # BUILD SYSTEM MATRIX
    ###################################################################  
    G = slippy.gbuild.build_system_matrix(obs_pos_cart_f, 
                                          patches_f,
                                          obs_basis_f,
                                          slip_basis_f, 
                                          leveling=True, 
                                          Nleveling=Nleveling,
                                          leveling_offset_sign=leveling_sign)

    # ### weigh system matrix and data by the uncertainty
    # ###################################################################  
    G /= obs_sigma_f[:,None]
    obs_disp_f /= obs_sigma_f  
    print("G:",np.shape(G));

    # regularization matrix (tikhonov regularization)
    print("L:",np.shape(L))

    # BUILD THE G MATRIX FOR THIS SET OF OBSERVATIONS
    G_ext, d_ext = G_with_smoothing(G, L, alpha, obs_disp_f);
    print("Gext (G,L,alpha):",np.shape(G_ext));
    
    # APPEND TO THE BIGGER MATRIX AND DATA VECTOR (WITH THE CORRECT SPANS)
    n_rows = len(d_ext);
    n_cols = n_model_params * n_epochs;
    G_rowblock_obs = np.zeros((n_rows, n_cols));  # one per observation
    G_nosmoothing_obs = np.zeros((np.shape(G)[0], n_cols));  # one per observation

    # Which spans does the data cover? This is like the "1" in SBAS
    # One new "rowblock" for each data file
    # Also build the G matrix that only has data (no smoothing)
    count=0;
    for epoch in total_spans:
      col_limits = [count*n_model_params, (count+1)*n_model_params];
      if epoch in this_data_spans:
        G_rowblock_obs[:,col_limits[0]:col_limits[1]] = G_ext;
        G_nosmoothing_obs[:,col_limits[0]:col_limits[1]] = G;
      count=count+1;

    # APPEND TO THE TOTAL MATRIX
    d_total = np.concatenate((d_total, d_ext));  # Building up the total data vector
    sig_total = np.concatenate((sig_total, obs_sigma_f));
    G_total = np.concatenate((G_total, G_rowblock_obs));
    G_nosmooth_total = np.concatenate((G_nosmooth_total, G_nosmoothing_obs));


  plt.figure(figsize=(12,8), dpi=300);
  plt.imshow(G_total,vmin=-0.02, vmax=0.02, aspect=1/3)
  plt.savefig("image_of_G.png");

  # INVERT BIG-G
  #   ### estimate slip and compute predicted displacement
  #   #####################################################################  
  slip_f = reg_nnls(G_total,d_total)
  print("G_total:", np.shape(G_total));
  print("slip_f:",np.shape(slip_f))
  print("G_nosmoothing_total:",np.shape(G_nosmooth_total));
  pred_disp_f = G_nosmooth_total.dot(slip_f)*sig_total; 

  total_cardinal_slip = parse_slip_outputs(slip_f, Ns_total, Ds, n_epochs, total_fault_slip_basis);
  disp_models = parse_disp_outputs(pred_disp_f, nums_obs);

  ### get slip patch data for outputs
  #####################################################################
  patches_pos_cart =[i.patch_to_user([0.5,1.0,0.0]) for i in patches]
  patches_pos_geo = plotting_library.cartesian_to_geodetic(patches_pos_cart,bm)
  patches_strike = [i.strike for i in patches]
  patches_dip = [i.dip for i in patches]
  patches_length = [i.length for i in patches]
  patches_width = [i.width for i in patches]


  # OUTPUT EACH SLIP INTERVAL
  for i in range(n_epochs): 
    one_span = total_spans[i];
    slip_output_file = span_output_files[i];

    # ### write output
    # #####################################################################
    slippy.io.write_slip_data(patches_pos_geo,
                              patches_strike,patches_dip,
                              patches_length,patches_width,
                              total_cardinal_slip[i],slip_output_file)


  # OUTPUT EACH PREDICTED DISPLACEMENT FIELD
  for filenum in range(len(input_file_list)):

    if data_type_list[filenum]=='gps':  # write GPS
      Ngps = int(nums_obs[filenum]/3);
      pred_disp_gps = disp_models[filenum];
      gps_output_file = config["output_dir"]+"dispmodel_"+input_file_list[filenum].split('/')[-1]
      pred_disp_gps = pred_disp_gps.reshape((Ngps,3))
      slippy.io.write_gps_data(pos_obs_list[filenum][::3], 
                           pred_disp_gps,0.0*pred_disp_gps,
                           gps_output_file);
      print("Writing file %s " % gps_output_file);

    elif data_type_list[filenum]=='uavsar':
      Npts = nums_obs[filenum];
      pred_disp_insar = disp_models[filenum];
      insar_output_file = config["output_dir"]+"dispmodel_"+input_file_list[filenum].split('/')[-1]
      slippy.io.write_insar_data(pos_obs_list[filenum],
                             pred_disp_insar,0.0*pred_disp_insar,
                             pos_basis_list[filenum], 
                             insar_output_file)
      print("Writing file %s " % insar_output_file );

    elif data_type_list[filenum]=='leveling' or data_type_list[filenum]=='tsx':
      Npts = nums_obs[filenum];
      pred_disp_leveling = disp_models[filenum];
      leveling_output_file = config["output_dir"]+"dispmodel_"+input_file_list[filenum].split('/')[-1]
      slippy.io.write_insar_data(pos_obs_list[filenum],
                             pred_disp_leveling,0.0*pred_disp_leveling,
                             pos_basis_list[filenum], 
                             leveling_output_file)
      print("Writing file %s " % leveling_output_file );

  return;


def parse_slip_outputs(slip_f,Ns_total, Ds, n_epochs, total_fault_slip_basis):
  print("Parsing slip outputs from %d epochs " % (n_epochs) );
  count = 0;
  total_cardinal_slip = [];
  for i in range(n_epochs):
    n_params = int(len(slip_f)/n_epochs);
    start = count;
    finish = count+n_params;
    slip_during_epoch = slip_f[start:finish];
    count = count + n_params; 
  
    slip_terms_only = slip_during_epoch[0:-1];  # LEVELING: Will ignore the last model parameter, which is the leveling offset
    leveling_offset = slip_during_epoch[-1];
    slip = slip_terms_only.reshape((Ns_total,Ds))  # THIS ASSUMES ALL FAULTS HAVE THE SAME NUMBER OF BASIS VECTORS
    cardinal_slip = slippy.basis.cardinal_components(slip,total_fault_slip_basis)
    total_cardinal_slip.append(cardinal_slip);
  
    print("Leveling Offset = %f m " % (leveling_offset) );
    if abs(leveling_offset)<0.0000001:
      print("WARNING for Epoch %d: Leveling offset close to zero. Consider a negative offset in G." % (i) ) 

  return total_cardinal_slip;

def parse_disp_outputs(pred_disp_f, num_obs):
  count=0;
  disp_segments = [];
  for i in range(len(num_obs)):
  	disp_segment = pred_disp_f[count:count+num_obs[i]]
  	disp_segments.append(disp_segment);
  	count=count+num_obs[i];
  return disp_segments;

