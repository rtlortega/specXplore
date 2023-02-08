# Developer Notes
# TODO: add max_spec = 50
#   Add a limiter to fragmap that prevents generation of a plot with more than 
#   50 spectra. At 50 spectra the y-axis becomes barely legible, and spectral 
#   differences crowd the plot so much that the x-axis requires very heavy zoom 
#   in, defeating the point of the visualization.
#   --> filter spectra to set of 50 most similar to root OR to 50 first indexed

from dash import html
from dash import dcc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import matchms
# import pickle

def generate_fragmap_panel(spec_ids, all_spectra):
    if spec_ids and len(spec_ids) >= 2:
        # TODO: incorporate Henry's fragmap scripts.
        spectra = [all_spectra[i] for i in spec_ids]
        step = 0.1
        bins = [round(x, 1) for x in list(np.arange(0, 1000 + step, step))]
        fragmap = generate_fragmap(id_list=list(range(0, len(spectra))),
            spec_list=spectra, rel_intensity_threshold=0.00000,
            prevalence_threshold=0, mz_min=0, mz_max=1000,
            bins=bins)
        out = [
            html.Div(dcc.Graph(id = "fragmap-panel", figure=fragmap, 
                style={"width":"100%","height":"60vh", 
                       "border":"1px grey solid"}))]
        return(out)
    else:
        out = [html.H6((
            "Select focus data and press " 
            "generate fragmap button for fragmap."))]
        return(out)

# generates long format data frame with spectral data columns id, mz, intensity
def spectrum_list_to_pandas(id_list: [int], 
    spec_list: [matchms.Spectrum]) -> pd.DataFrame:
    """
    Description
    """
    # Ensure the provided ID list is valid
    assert all([ind in range(0, len(spec_list)) for ind in id_list]), (
        f"Error: Provided ID list {id_list} contains ID's which do not" 
        f"match the spec_list of length {len(spec_list)}."
    )
    # Initialize empty list of data frames
    spec_data = list()
    for identifier in id_list:
        spec_data.append(pd.DataFrame({
            "spectrum": identifier, 
            "mz": spec_list[identifier].peaks.mz, # OLD MATCHMS SYNTAX
            #"mz": spec_list[identifier].mz, # NEW MATCHMS SYNTAX
            #"intensity": spec_list[identifier].intensities # NEW MATCHMS SYNTAX
            "intensity": spec_list[identifier].peaks.intensities # OLD MATCHMS SYNTAX
            }))
    # Return single long data frame
    long = pd.concat(objs=spec_data, ignore_index=True)
    return long



def bin_spectra(spectra: pd.DataFrame, bins: [float]) -> pd.DataFrame:
    """
    Description

    """

    # Generalize to work with single spectrum object
    # return binned spectrum object
    # aggregate mz values into bins with intensity
    # spectrum object with modified mz and intensity values to correspond directly to bins

    # Bin Spectrum Data
    index_bin_map = pd.cut(
        x=spectra["mz"], bins=bins, labels=bins[0:-1], include_lowest=True)
    spectra.insert(
        loc=2, column="bin", value=index_bin_map, allow_duplicates=True)

    # Return Binned Data as long pandas dataframe
    return spectra


def filter_binned_spectra_by_frequency(
    binned_spectra: pd.DataFrame, n_bin_cutoff: int):
    """
    Clean up binned data in place
    """

    # TODO: turn input into list of spectra (binned, but still simple spectra)
    # Simply a filter for max number of mz int tuples by sorted intensity

    # Count the total number of unique bins the dataset. Return if below threshold
    unique_bins = np.unique(binned_spectra['bin'].tolist())
    if len(unique_bins) <= n_bin_cutoff:
        return
    # Count the number of occurrences per bin
    bin_counts = binned_spectra.groupby(
        by="bin", axis=0, as_index=False, observed=True).size()
    bin_counts.sort_values(
        by="size", axis=0, ascending=False, inplace=True, ignore_index=True)

    # Filter Binned Spectra in place
    bins_to_keep = bin_counts.head(n=n_bin_cutoff)["bin"].tolist()
    binned_spectra.drop(
        labels=binned_spectra.loc[~binned_spectra["bin"].isin(bins_to_keep)].index, inplace=True)
    binned_spectra.reset_index(inplace=True, drop=True)



# ALERT: THE PRECURSOR MAY NOT BE A PEAK IN THE MS2 SPECTRUM. USE get_precursor() from matchms instead.
# the precursor also certainly has nothing to do with highest intensity.
# REMOVE ONCE FIXED
def get_precursors(
    id_list: [int], spec_list: [matchms.Spectrum]) -> {int: float}:
    # Initialize emtpy dictionary of precursors
    precursors = {spectrum: -1.0 for spectrum in id_list}
    # Iterate over all id's in ID-list
    for ind in id_list:
        # Identify the spectrum with the highest intensity, and save as precursor
        #max_peak_index = np.argmax(spec_list[ind].intensities) # NEW MATCHMS SYNTAX
        max_peak_index = np.argmax(spec_list[ind].peaks.intensities) # OLD MATCHMS SYNTAX
        #precursors[ind] = spec_list[ind].mz[max_peak_index] # NEW MATCHMS SYNTAX
        precursors[ind] = spec_list[ind].peaks.mz[max_peak_index] # OLD MATCHMS SYNTAX
    # Return dictionary of precursors, indexed by spectrum ID's
    return precursors

# specxplore dataclass spectrum
# generate only neutral losses --> list of mz, list of intensities ==> np.arrays()
def calculate_neutral_loss(
    spectrum: matchms.Spectrum, precursor: float) -> ([float], [float]):
    # Determine the number of peaks and the index of the precursor therein
    #p_index, n_peaks = np.where(spectrum.mz == precursor), len(spectrum.mz) # NEW MATCHMS SYNTAX
    p_index, n_peaks = np.where(spectrum.peaks.mz == precursor), len(spectrum.peaks.mz) # OLD MATCHMS SYNTAX
    # Calculate the adjusted mz values, but ignore the precursor index
    # 
    mz_adj = [
        abs(spectrum.peaks.mz[i] - precursor) # OLD MATCHMS SYNTAX
        #abs(spectrum.mz[i] - precursor) # NEW MATCHMS SYNTAX
        for i in range(0, n_peaks) 
        if i != p_index]
    

    intensities = [
        #spectrum.intensities[i] # NEW MATCHMS SYNTAX
        spectrum.peaks.intensities[i] # OLD MATCHMS SYNTAX
        for i in range(0, n_peaks) 
        if i != p_index]
    # Return adjusted mz values and corresponding intensities
    return mz_adj, intensities

# get as input precursor and mz and int; do not require subselection in this; only pass relevant
# generate list of datclass spectrums
# create func to generate the pandas df / whatever needed for the plot
def get_neutral_losses(id_list: [int], spec_list: [matchms.Spectrum]) -> pd.DataFrame:
    """
    Description
    """
    # Get Precursors
    precursors = get_precursors(id_list=id_list, spec_list=spec_list)
    # Initialize list of pandas to contain the neutral loss data
    neutral_loss_data = list()
    # Iterate over all indices specified or all indices in the data
    for ind in id_list:
        # Extra data, create pandas data frame, and append to growing list data frames
        neutral_loss_mz, neutral_loss_intensities = calculate_neutral_loss(
            spectrum=spec_list[ind], precursor=precursors[ind])
        neutral_loss_data.append(pd.DataFrame({
            "spectrum": ind,
            "mz": neutral_loss_mz,
            "intensity": neutral_loss_intensities}))

    # Concatenate all data into singular long pandas
    return pd.concat(objs=neutral_loss_data, ignore_index=True)

# THIS CAN BE REPLACED WITH MATCHMS FILTERS FOR MZ BOUNDS, INTENSITY AND MAX NUMBER OF PEAKS
# 3 lines of code.
def filter_binned_spectra(spectra: pd.DataFrame,
                          intensity_threshold: float,
                          prevalence_threshold: int,
                          mz_bounds: (float, float),
                          to_discard=None) -> [int]:
    """
    Description
    """
    #for each spec:
    #    filter_intensity (each spectrum) # get ridd of noise
    #    filter_mz (each spectrum) # limit to range
    
    # filter prevalence would work in a single line when using pd filters
    #filter_prevalence (list of spectra) # avoid non-overlaps

    # Initialize a list of bins to remove if they do not meet the criteria set
    to_discard = list() if to_discard is None else to_discard
    # Iterate over all bins in the current spectra dataset
    all_bins = np.unique(spectra["bin"].tolist())
    for current_bin in all_bins:
        # If the bin has already been flagged for removal, continue
        if current_bin in to_discard:
            continue
        # If the current bin's mz values do not fall within the specified range, remove
        if mz_bounds[0] > current_bin or mz_bounds[1] <= current_bin:
            to_discard.append(current_bin)
            continue
        # Extract all data of the current bin
        bin_data = spectra.loc[spectra['bin'] == current_bin]
        # If the bin has too few spectra featured within it, discard
        if bin_data.shape[0] < prevalence_threshold:
            to_discard.append(current_bin)
            continue
        # If all the bin's intensities are below the threshold, discard
        if all(intensity < intensity_threshold for intensity in bin_data["intensity"].tolist()):
            to_discard.append(current_bin)
            continue
    # Filter out all the
    spectra.drop(
        labels=spectra.loc[spectra["bin"].isin(to_discard)].index, 
        inplace=True)
    spectra.reset_index(inplace=True, drop=True)
    # Return the list of bins discarded
    return to_discard


# generate_x_axis_labels_for_bins()
# bins = all_observed_mz_values (binned)
def get_bin_map(bins: [int]):
    # Get all unique bins and sort them in ascending order
    unique_bins = np.unique(bins)
    unique_bins.sort()
    # Create mapping of bins to integers based on ascending order
    integer_map = {bin_id: index for index, bin_id in enumerate(unique_bins)}
    # Return a list of bins mapped to corresponding integer values
    return integer_map

# generate_y_axis_labels_for_specs
# input to get_spectrum_map should ??? contain actual spec_ids for y axis labelling.
# beware of non-iloc downstream effects
def get_spectrum_map(spectra: [int], root: int):
    assert root in spectra, (
        f"Error: Root Spectrum {root} not present in provided spectrum list."
    )
        
    # Get all unique spectra and sort them (without root, which will be the first)
    # TODO: other types of sorting in case spectrum ID's are not integers?
    
    # pandas specific artefacts since ids may now be duplicated
    unique_spectra = np.unique(spectra)
    unique_spectra = [ spectrum for spectrum in unique_spectra if spectrum != root]

    unique_spectra.sort()
    
    # TODO: double check indexing validity
    integer_map = {
        spectrum: index + 1 
        for index, spectrum in enumerate(unique_spectra) 
        if spectrum != root}
    
    integer_map[root] = 0
    return integer_map

# plot data generator function that creates input for heatmap
# this is where the pandas aggregation should happen
def get_spectrum_plot_data(
    binned_spectra: pd.DataFrame, spectrum_map: {int: int}, 
    bin_map: {int: int}):
    """
    Description
    """
    # Map Bins and Spectra to their new continuous values for plotting


    # create list of mapped spectra
    # 1 row for each spec_id and y_index tuple
    # key indexing, get for each spectrum_identifier the corresponding y_index continuous position

    # [spectrum_map[spectrum] for spectrum in binned_spectra["spectrum"].tolist()]

    new_data_frame = pd.DataFrame({
        "spectrum": [spectrum_map[spectrum] for spectrum in binned_spectra["spectrum"].tolist()],
        "bin": [bin_map[bin_id] for bin_id in binned_spectra["bin"].tolist()], # integer for x_axis
        "mz": binned_spectra["mz"].tolist(), # --> actual mz values for each x_axis thing; could be tuple
        "intensity": binned_spectra["intensity"].tolist()
    })
    # Return Mapped Dataset
    return new_data_frame


def get_binned_spectrum_trace(binned_spectra: pd.DataFrame):
    # Create Heatmap Trace
    # TODO: parameterize the gaps in terms of the x and y axis instead of pixels
    # TODO: ADD HOVERETEMPLATE TO GIVE MEANING TO TEXT ADDITION (LIST OF MZ VALUES AGGREGATED INTO BIN)
    heatmap_trace = go.Heatmap(x=binned_spectra["bin"].tolist(),
                               y=binned_spectra["spectrum"].tolist(),
                               z=binned_spectra["intensity"].tolist(),
                               text = binned_spectra["mz"].tolist(),
                               xgap=5,
                               ygap=5, 
                               colorscale = "blugrn")

    # Return Heatmap Trace
    return heatmap_trace


# generate_neutral_loss_shape_list()
# THIS IS NOT THE BINNED SPECTRA, BUT BINNED NEUTRAL LOSSES NOW CONCATENATED TO A PD.DATAFRAME
# THE NEUTRAL NEED TO BE BINNED
def get_binned_neutral_trace(binned_spectra: pd.DataFrame):

    # Radius of Points
    r = 0.2
    # TODO: ADD N_ROWS PARAMETER

    # Create Point Scatter of neutral losses
    # 'line_color':'orange', 'line_width' : 0.5 # --> border lines with
    # different colors help visual clarity, but introduce border sizing
    # artefacts
    kwargs = {'type': 'circle', 'xref': 'x', 'yref': 'y', 'fillcolor': 'red', 
        'opacity' : 1}
    shapes = [
        go.layout.Shape(
            x0=binned_spectra.iloc[row]["bin"] - r,
            y0=binned_spectra.iloc[row]["spectrum"] - r,
            x1=binned_spectra.iloc[row]["bin"] + r,
            y1=binned_spectra.iloc[row]["spectrum"] + r,
            **kwargs) 
        for row 
        in range(0, binned_spectra.shape[0])]

    # Return the points trace
    return shapes


def generate_fragmap(id_list: [int], spec_list: [matchms.Spectrum], 
    rel_intensity_threshold: float, prevalence_threshold: int, mz_min: float,
    mz_max: float, bins: [float], root: int = 0, n_bin_cutoff: int = 200):
    """
    Wrapper function that executes complete generate fragmap routine and 
    returns final fragmap as plotly graph object.

    Arguments:
        id_list: A list of spectrum id's (int list index)
        spec_list: An ordered list of matchms spectra (aligned with numeric 
            list index)
        rel_intensity_threshold: Float input. Minimum value of intensity a 
            fragment needs to reach in at least one spectrum.
        prevalence_threshold: integer input. Minimum number of occurences of 
            bin across selected spectrum set.
        mz_max: Maximum mz value for a bin to be considered.
        mz_min: Minimum mz value for a bin to be considered.
        bins: a list of floats / integers mapping out the bin edges to be used
        root: 0 - Index of the primary spectrum. For now assumed 0.
        n_bin_cutoff: the maximum number of bins to display
    """


    # filter raw data - add settings to dashboard
    # filter prevalence - make optional, add setting to dashboard
    
    # construct set() of bins --> input for fast neutral loss suitability checks
    
    # neutral loss computation
    # neutral losses should be exclusively in the existing bin set


    # Step 1: Construct Binned Spectra
    spectra_long = spectrum_list_to_pandas(
        id_list=id_list, spec_list=spec_list)
    binned_spectra = bin_spectra(spectra=spectra_long, bins=bins)

    # Step 2: Filter Binned Spectra
    filter_binned_spectra_by_frequency(
        binned_spectra=binned_spectra, n_bin_cutoff=n_bin_cutoff)
    remaining_bins = np.unique(binned_spectra["bin"].tolist())


    # Step 3-1: Calculate and Bin Neutral Losses
    neutral_losses = get_neutral_losses(id_list=id_list, spec_list=spec_list)
    binned_neutral = bin_spectra(spectra=neutral_losses, bins=bins)

    # Step 3-2: Keep only those bins featured in the binned spectrum set
    binned_neutral.drop(
        labels=binned_neutral.loc[
            ~binned_neutral["bin"].isin(remaining_bins)].index, 
            inplace=True)
    binned_neutral.reset_index(inplace=True, drop=True)


    # THIS SHOULD BE IN THE BEGINNING TO LIMIT NUMBER OF FRAGMENTS CONSIDERED
    # Step 4-1: Filter Binned Spectra
    discarded_bins = filter_binned_spectra(
        spectra=binned_spectra, intensity_threshold=rel_intensity_threshold,
        prevalence_threshold=prevalence_threshold,
        mz_bounds=(mz_min, mz_max))

    # THIS SECOND STEP SEEMS SUPERFLUOUS
    #
    # Step 4-2: Filter Neutral Losses (propagate forward the already removed 
    # bins)
    discarded_bins = filter_binned_spectra(
        spectra=binned_neutral, intensity_threshold=rel_intensity_threshold,
        prevalence_threshold=prevalence_threshold, mz_bounds=(mz_min, mz_max),
        to_discard=discarded_bins)

    
    # Step 5-1: Create Map of Bins and Spectra to Integers
    spectrum_map = get_spectrum_map(
        spectra=binned_spectra["spectrum"].tolist(), root=root)
    bin_map = get_bin_map(bins=binned_spectra["bin"].tolist())
    # Step 5-2: Map both binned spectra and neutral losses dataframes to the 
    # new integer set
    spectra_mapped = get_spectrum_plot_data(
        binned_spectra=binned_spectra, spectrum_map=spectrum_map, 
        bin_map=bin_map)
    neutral_mapped = get_spectrum_plot_data(
        binned_spectra=binned_neutral, spectrum_map=spectrum_map, 
        bin_map=bin_map)



    # construct_heatmap_df (contains both mz and neutral losses)
    # apply_prevalence_filter to heatmap_df
    # isolate trace data --> mz_df, neutral_df


    # plot objects (with separate dfs)
    # --> two trace generations
    # Add layout and styling to plot function
    
    # Step 6-1: Create Individual Traces
    heatmap_trace = get_binned_spectrum_trace(binned_spectra=spectra_mapped)
    points_trace = get_binned_neutral_trace(binned_spectra=neutral_mapped)
    # Step 6-2: Combine Traces and Style Figure
    fragmentation_map = go.Figure(data=[heatmap_trace])
    fragmentation_map.update_layout(
        # Add Neutral Loss Points Trace
        shapes=points_trace,
        # Change Theme
        template="simple_white", 
        # Lock aspect ratio of heatmap and relabel the y-axis
        yaxis=dict(
            #scaleanchor='x',
            fixedrange=True,
            tickmode='array',
            tickvals=list(spectrum_map.values()),
            ticktext=list(spectrum_map.keys())
        ),
        # relabel the x-axis
        xaxis=dict(
            tickmode='array',
            tickvals=list(bin_map.values()),
            ticktext=list(bin_map.keys())
        ),
        margin = {"autoexpand":True, "b" : 10, "l":10, "r":10, "t":10}
    )
    return fragmentation_map