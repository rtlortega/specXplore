from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from collections import namedtuple
import typing
from typing import List, TypedDict, Tuple, Dict, NamedTuple, Union
import copy
from specxplore import importing_cython
from specxplore import utils
from specxplore.netview import SELECTED_NODES_STYLE, GENERAL_STYLE, SELECTION_STYLE
import os
import json 
import pickle
import matchms

from kmedoids import KMedoids
from sklearn.metrics import silhouette_score
from scipy.spatial.distance import pdist, squareform
from scipy.stats import pearsonr, spearmanr  
from sklearn.manifold import TSNE
import plotly.graph_objects as go
import plotly.express


import matchms.utils 
import json
import urllib
import time
import os
import gensim
from spec2vec import Spec2Vec
import matchms
from matchms import calculate_scores
from matchms.similarity import CosineGreedy, ModifiedCosine, CosineHungarian
#from ms2query.utils import load_matchms_spectrum_objects_from_file
from ms2deepscore import MS2DeepScore
from ms2deepscore.models import load_model
import copy
import numpy as np
import pandas as pd
from collections import namedtuple
from networkx import read_graphml
from networkx.readwrite import json_graph




@dataclass
class KmedoidGridEntry():
    """ 
    Container Class for K medoid clustering results.

    Parameters:
        k: the number of clusters set.
        cluster_assignments: List with cluster assignment for each observation.
        silhouette_score: float with clustering silhouette score.
    """
    k : int
    cluster_assignments : List[int]
    silhouette_score : float
    random_seed_used : int
    def __str__(self) -> str:
        """ Custom Print Method for kmedoid grid entry producing an easy readable string output. """
        custom_print = (
            f"k = {self.k}, silhoutte_score = {self.silhouette_score}, \n"
            f"cluster_assignment = {', '.join(self.cluster_assignments[0:7])}...")
        return custom_print
    

@dataclass
class TsneGridEntry():
    """ 
    Container Class for K medoid clustering results.

    Parameters:
        k: the number of clusters aimed for.
        cluster_assignments: List with cluster assignment for each observation.
        silhouette_score: float with clustering silhouette score.
    """
    perplexity : int
    x_coordinates : List[int]
    y_coordinates:  List[int]
    pearson_score : float
    spearman_score : float
    random_seed_used : float
    def __str__(self) -> str:
        custom_print = (
            f"Perplexity = {self.perplexity}," 
            f"Pearson Score = {self.pearson_score}, "
            f"Spearman Score = {self.spearman_score}, \n"
            f"x coordinates = {', '.join(self.x_coordinates[0:4])}...",
            f"y coordinates = {', '.join(self.y_coordinates[0:4])}...")
        return custom_print

@dataclass
class Spectrum:
    """ Spectrum data class for storing basic spectrum information and neutral loss spectra. 

    Parameters:
    :param mass_to_charge_ratio: np.ndarray of shape(1,n) where n is the number of mass to charge ratios.
    :param precursor_mass_to_charge_ratio: np.double with mass to charge ratio of precursor.
    :param identifier: np.int64 is the spectrum's identifier number.
    :param intensities: np.ndarray of shape(1,n) where n is the number of intensities.
    :param mass_to_charge_ratio_aggregate_list: List[List] containing original mass to charge ratios merged 
        together during binning.
    :param intensity_aggregate_list: List[List] containing original intensity values merged together during binning.
    :param binned_spectrum: Bool, autodetermined from presence of aggregate lists to specify that the spectrum has been 
        binned.
    Raises:
        ValueError: if shapes of intensities and mass_to_charge_ratio arrays differ.
        ValueError: if length mismatches in List[List] structures for aggregate lists if provided.
    
    Developer Notes: 
    Spectrum identifier should correspond to the iloc of the spectrum in the orginal spectrum list used in specxplore.
    There are no checks in place within the Spectrum object to make sure this is the case.
    Intensities are not necessary as an input. This is to accomodate neutral loss mock spectra objects. If no 
    intensities are provided, intensity values are set to np.nan assuming neutral loss spectra were provided.
    Aggregate lists are an optional input an by-product of binning. If no two mz values were put into the same mass-
    to-charge-ratio bin, then the aggregate lists contains only lists of len 1.
    """
    mass_to_charge_ratios : np.ndarray #np.ndarray[int, np.double] # for python 3.9 and up
    precursor_mass_to_charge_ratio : np.double
    spectrum_iloc : np.int64
    intensities : np.ndarray
    feature_id : np.string_

    # TDOD fix tuple to list of list
    mass_to_charge_ratio_aggregate_list : field(default_factory=tuple) = ()
    intensity_aggregate_list : field(default_factory=tuple) = ()
    is_binned_spectrum : bool = False
    is_neutral_loss : bool = False
    
    def __post_init__(self):
        """ Assert that data provided to constructor is valid. """
        assert self.intensities.shape == self.mass_to_charge_ratios.shape, (
            "Intensities (array) and mass to charge ratios (array) must be equal shape."
        )
        if (
            self.intensity_aggregate_list 
            and self.mass_to_charge_ratio_aggregate_list
            ):
            self.is_binned_spectrum = True
            assert len(self.mass_to_charge_ratio_aggregate_list) == len(self.intensity_aggregate_list), (
                "Bin data lists of lists must be of equal length."
            )
            for x,y in zip(self.intensity_aggregate_list, self.mass_to_charge_ratio_aggregate_list):
                assert len(x) == len(y), (
                    "Sub-lists of aggregate lists must be of equal length, i.e. for each"
                    " mass-to-charge-ratio there must be an intensity value at equal List[sublist] position."
                )

@dataclass
class session_data:
    ''' 
    session_data is a constructor class that allow creating all variables for running specxplore dashboards. 
    
    It comprises of a initiator making use of a matchms spectrum list and a path to a model folder to construct pairwise 
    similarity matrices, define spectrum_iloc and feature_id mapping, and constructs the list of specXplore spectra used 
    within the dashboard visualizations. Any spectra data processing is assumed to have been done before initating the 
    session_data object.
    
    Usage Workflow:
    ---------------

    A number of essential variables for specXplore are left as None after initition and have to be constructed using 
    additional information. The expected sequence of calls is as follows:

    0) Initiate the session_data object using the constructor and matchms spectrum list.
    1) Run the tsne-grid and select a tsne coordinate system using 
       self.attach_tsne_grid() and 
       self.select_tsne_coordinates()
    2) Run the kmedoid-grid and select a single or range of k classifications to add to the class table via
       self.attach_kmedoid_grid() and 
       self.select_kmedoid_cluster_assignments()
    3) Attach any metadata from ms2query or elsewhere via 
       self.attach_addon_data_to_metadata()
    4) Attach any additional class table variables via 
       self.attach_addon_data_to_class_table()
    5) Initialize dashboard visual and network variables once all is information included into the session data via
       self.initialize_specxplore_session()

    Note the in all above calls, 'self' has to be replaced with the chosen variable name for the session data object.
    '''
    def __init__(
            self,
            spectra_list_matchms: List[matchms.Spectrum], 
            models_and_library_folder_path : str
            ):
        ''' Constructs Basic Scaffold for specXplore session without coordinate system or any metadata. '''
        
        # Making sure that the spectra provided are valid and contain all required information:
        for spectrum in spectra_list_matchms:
            assert spectrum is not None, (
                "None object detected in spectrum list. All spectra must be valid matchms.Spectrum instances."
            )
            assert spectrum.get("feature_id") is not None, (
                "All spectra must have valid feature id entries."
            )
            assert spectrum.get("precursor_mz") is not None, (
                "All spectra must have valid precursor_mz value."
            )
        feature_ids = [str(spec.get("feature_id")) for spec in spectra_list_matchms]
        assert len(feature_ids) == len(set(feature_ids)), ("All feature_ids must be unique.")
        
        # Convert spectra for specXplore visualization modules
        self.spectra = convert_matchms_spectra_to_specxplore_spectra(spectra_list_matchms)
        self.init_table = construct_init_table(self.spectra)

        # Construct pairwise similarity matrices from matchms spectra
        self.scores_spec2vec = compute_similarities_s2v(
            spectra_list_matchms, models_and_library_folder_path
        )
        self.scores_modified_cosine = compute_similarities_cosine(
            spectra_list_matchms, 
            cosine_type="ModifiedCosine"
        )
        self.scores_ms2deepscore = compute_similarities_ms2ds(
            spectra_list_matchms, models_and_library_folder_path
        )

        # Initialize data tables to None
        self.metadata_table = copy.deepcopy(self.init_table)
        self.tsne_coordinates_table = None
        self.class_table = None # includes feature_id and spectrum_iloc inside specXplore, but getter only returns classes part of table
        self.highlight_table = None

        self.class_dict = None 
        self.available_classes = None
        self.selected_class_data = None
        self.initial_style = None
        self.initial_node_elements = None
    
    def initialize_specxplore_session(self) -> None:
        ''' Wrapper for cosmetic and quantitative network variable initialization based on input data. '''

        self.initialize_specxplore_dashboard_variables()
        self.construct_derived_network_variables()
        self.initial_node_elements = utils.initialize_cytoscape_graph_elements(
            self.tsne_coordinates_table, 
            self.selected_class_data, 
            self.highlight_table['highlight_bool'].to_list()
        )
        return None


    def initialize_specxplore_dashboard_variables(self) -> None:
        ''' Construct variables derived from input that are used inside the dashboard. 
        
        These will be internal, private style variables, left accessible to the user however. 
        '''
        
        class_table = self.get_class_table()
        self.class_dict = {
            elem : list(class_table[elem]) 
            for elem in class_table.columns
        } 
        self.available_classes = list(self.class_dict.keys())
        self.selected_class_data = self.class_dict[self.available_classes[0]] # initialize default
        self.initial_style = SELECTED_NODES_STYLE + GENERAL_STYLE + SELECTION_STYLE
        return None
    

    def construct_derived_network_variables(self) -> None:
        ''' Construct the edge lists and include init styles for specxplor dashboard '''

        sources, targets, values = importing_cython.construct_long_format_sim_arrays(
            self.scores_ms2deepscore
        )  
        ordered_index = np.argsort(-values)
        sources = sources[ordered_index]
        targets = targets[ordered_index]
        values = values[ordered_index]
        self.sources = sources
        self.targets = targets
        self.values = values
        return None
    
    def attach_addon_data_to_metadata(self, addon_data : pd.DataFrame) -> None:
        """ Attach additional metadata contained within pd.DataFrame to existing metadata via feature_id overlap. """
        # Metadata table always initiated to init_table
        self.metadata_table = attach_columns_via_feature_id(
            self.metadata_table, 
            addon_data
        )
        return None
    

    def attach_addon_data_to_class_table(self, addon_data : pd.DataFrame) -> None:
        """ 
        Attach additional classdata contained within pd.DataFrame to existing class_table via feature_id overlap. 
        """
        # Class table may not have been initiated
        if self.class_table is None:
            self.class_table = copy.deepcopy(self.init_table)
        self.class_table = remove_white_space_from_df(
            attach_columns_via_feature_id(self.class_table, addon_data)
        )
        return None


    def attach_run_tsne_grid(
            self, 
            perplexity_values : List[int], 
            random_states : Union[List, None] = None
            ) -> None:
        """ Generate and attach t-SNE grid """
        
        distance_matrix = convert_similarity_to_distance(self.scores_ms2deepscore)
        self.tsne_grid = run_tsne_grid(
            distance_matrix, 
            perplexity_values, 
            random_states
        )
        print_tsne_grid(self.tsne_grid)
        return None


    def attach_kmedoid_grid(
            self, k_values : List[int], 
            random_states : Union[List, None] = None
            ) -> None:
        """ Generate and attach kmedoid grid """

        distance_matrix = convert_similarity_to_distance(self.scores_ms2deepscore)
        self.kmedoid_grid = run_kmedoid_grid(
            distance_matrix, 
            k_values, 
            random_states
        ) 
        print_kmedoid_grid(self.kmedoid_grid)
        return None


    def select_tsne_coordinates(self, scalar_iloc : int) -> None:
        """ Select a tsne coordinate system from kmedoid grid via iloc in grid list. """

        assert self.tsne_grid is not None, (
            'No tsne grid detected. Run attach_tsne_grid to be able to'
            ' be able select a kmedoid grid entry.'
        )
        assert isinstance(scalar_iloc, int), 'scalar_iloc must be single type int variable'
        assert scalar_iloc in [i for i in range(0, len(self.tsne_grid))]
        
        # construct tsne table
        if self.tsne_coordinates_table is None:
            self.tsne_coordinates_table = copy.deepcopy(self.init_table)
        
        # Extract relevant tsne_grid entry & attach coordinates
        tsne_entry = self.tsne_grid[scalar_iloc]

        # only t-sne coordinates are written / overwritten
        self.tsne_coordinates_table ['x'] = tsne_entry.x_coordinates
        self.tsne_coordinates_table ['y'] = tsne_entry.y_coordinates
        return None


    def select_kmedoid_cluster_assignments(self, iloc_list : List[int]) -> None:
        """ Select one or more kmedoid k levels for class table via ilocs in grid list. """
        
        assert isinstance(iloc_list, list), 'iloc list must be type list. If only one value, use [value]'
        assert self.kmedoid_grid is not None, (
            'No kmedoid grid detected. Run attach_kmedoid_grid to be able to'
            ' be able select a kmedoid grid entry.'
        )
        for iloc in iloc_list:
            assert isinstance(iloc, int), 'iloc must be single type int variable'
            assert iloc in [i for i in range(0, len(self.kmedoid_grid))]
        
        # construct kmedoid class table / attach to class_tablw
        if self.class_table is None:
            self.class_table = copy.deepcopy(self.init_table)
        
        selected_subgrid = [self.kmedoid_grid[iloc] for iloc in iloc_list]
        kmedoid_table = pd.DataFrame(
            data = {
                "K = " + str(elem.k) : elem.cluster_assignments 
                for elem in selected_subgrid
            }
        )
        kmedoid_table = kmedoid_table.loc[
            :, 
            ~kmedoid_table.columns.isin(
                self.class_table.columns.to_list()
            )
        ]
        self.class_table = pd.concat([self.class_table, kmedoid_table], axis=1, join='inner')
        return None
    

    def reset_class_table(self) -> None:
        """ Resets specXplore class_table entry to None. """
        self.class_table = None
        return None
    

    def reset_metadata_table(self) -> None:
        """ Resets specXplore class_table entry to None. """
        self.metadata_table = self.init_table
        return None
    

    def get_tsne_coordinates_table(self) -> pd.DataFrame:
        ''' Getter for t-sne coordinates table that attaches the highlight table if available or adds a default. '''

        assert self.tsne_coordinates_table is not None, 'tsne_coordinates_table does not exist and cannot be returned.'
        
        output_table = copy.deepcopy(self.tsne_coordinates_table)
        if self.highlight_table is None: # no features selected for highlighting
            output_table['highlight_bool'] = False
        else:
            output_table['highlight_bool'] = copy.deepcopy(
                self.highlight_table["highlight_bool"]
            )
        return output_table
    

    def get_class_table(self) -> pd.DataFrame:
        """ Returns class table for use within specXplore; omits spectrum_iloc and feature_id columns. """

        assert self.class_table is not None, 'class_table does not exist and cannot be returned.'
        output_table = copy.deepcopy(
            self.class_table.loc[
                :, 
                ~self.class_table.columns.isin( ["spectrum_iloc", "feature_id"] )
            ]
        )
        return output_table
    

    def get_metadata_table(self) -> pd.DataFrame:
        """ Returns a copy of the metadata table. """
        assert self.metadata_table is not None, 'class_table does not exist and cannot be returned.'
        output_table = copy.deepcopy(self.metadata_table)
        return output_table
    
    
    def construct_highlight_table(
            self, 
            feature_ids : List[str]
            ) -> None:
        ''' 
        Construct the table of features considered knowns or standards for visual highlighting in specXplore overview. 
        
        Input:
            feature_id: list of str entries specifying the feature_ids worth highlighting in specXplore. Usually 
                spike-in standards or high confidence library matches.
        Attaches:
            highlight table with features to be highlighted.

        Developer Notes:
            This function can be used with init tables, but also with the t-SNE table directly sicne the relevant entries
            are available.
        Requires a init table and feature_ids designated for highlighting.
        '''

        feature_set = set(feature_ids)
        highlight_table = copy.deepcopy(self.init_table)
        highlight_table['highlight_bool'] = [
            elem in feature_set 
            for elem in self.init_table["feature_id"]
        ]
        self.highlight_table = highlight_table
        return None
    

    def get_spectrum_iloc_list(self) -> List[int]:
        """ Return list of all spectrum_iloc """

        return self.init_table['spectrum_iloc'].to_list()

    def check_and_save_to_file(self, filepath : str) -> None:
        """ Saves specxplore data object using pickle provided all data elements available."""

        assert self.class_table is not None, (
            'class_table not found. incomplete specxplore object cannot be saved or loaded'
            'Run and select k-medoid classification or provide classification table.'
        )
        assert self.highlight_table is not None, (
            'highlight_table not found. incomplete specxplore object cannot be saved or loaded'
        )
        assert self.metadata_table is not None, (
            'metadata_table not found. incomplete specxplore object cannot be saved or loaded'
            'Initialize metadata table.'
        )
        assert self.tsne_coordinates_table is not None, (
            'Variable tsne_coordinates_table not found. Incomplete specxplore object cannot be saved or loaded.'
            'Select and attach t-SNE x y coordinate system for features.'
        )
        assert self.values is not None, (
            'Variable values not found. Incomplete specxplore object cannot be saved or loaded'
            'Initalize specxplore object before attempting save.'
        )
        assert self.targets is not None, (
            'Variable targets not found. Incomplete specxplore object cannot be saved or loaded.'
            'Initalize specxplore object before attempting save.'
        )
        assert self.sources is not None, (
            'Variable sources not found. Incomplete specxplore object cannot be saved or loaded.'
            'Initalize specxplore object before attempting save.'
        )
        with open(filepath, 'wb') as file:
            pickle.dump(self, file)
        return None


    def save_selection_to_file(
            self, 
            filepath : str, 
            selection_idx : List[int]
            ) -> None:
        ''' 
        Functions copies current session_data objects and replaces all member variables with subselection
        before saving to file. Overwriting a copy is done to avoid making the user facing constructor more 
        complicated (overloading not possible in python)

        Selection_idx correspond to selected spectrum_iloc in the current specXplore session data.

        Beware: tsne coordinates will not be optimal for arbitrary data sub-selections.
        '''
        
        assert len(selection_idx) >= 2, "specXplore object requires at least 2 spectra to be selected."

        # subset data structures
        scores_ms2deepscore = self.scores_ms2deepscore[selection_idx, :][:, selection_idx].copy()
        scores_spec2vec = self.scores_spec2vec[selection_idx, :][:, selection_idx].copy()
        scores_modified_cosine = self.scores_modified_cosine[selection_idx, :][:, selection_idx].copy()
        
        tsne_coordinates_table = self.tsne_coordinates_table.iloc[selection_idx].copy()
        
        metadata_table = self.metadata_table.iloc[selection_idx].copy()
        class_table = self.class_table.iloc[selection_idx].copy()
        init_table = self.init_table.iloc[selection_idx].copy()
        highlight_table = self.highlight_table.iloc[selection_idx].copy()

        new_spectrum_iloc = [idx for idx in range(0, len(selection_idx))]
        metadata_table['spectrum_iloc'] = new_spectrum_iloc
        metadata_table.reset_index(drop=True, inplace=True)
        class_table['spectrum_iloc'] = new_spectrum_iloc
        class_table.reset_index(drop=True, inplace=True)
        init_table['spectrum_iloc'] = new_spectrum_iloc
        init_table.reset_index(drop=True, inplace=True)
        highlight_table['spectrum_iloc'] = new_spectrum_iloc
        highlight_table.reset_index(drop=True, inplace=True)
        spectra = copy.deepcopy(self.spectra) # make a deep copy to detach from actual spectrum list
        spectra = [self.spectra[idx] for idx in selection_idx] # subset spectrum list
        
        # Create a coopy of the current session and overwrite variables
        # Current specXplore session data constructor lacks constructor for member variables available already!
        new_specxplore_session = copy.deepcopy(self)
        new_specxplore_session.scores_ms2deepscore = scores_ms2deepscore
        new_specxplore_session.scores_modified_cosine = scores_modified_cosine
        new_specxplore_session.scores_spec2vec = scores_spec2vec
        new_specxplore_session.tsne_coordinates_table = tsne_coordinates_table
        new_specxplore_session.metadata_table = metadata_table
        new_specxplore_session.class_table = class_table
        new_specxplore_session.init_table = init_table
        new_specxplore_session.highlight_table = highlight_table
        new_specxplore_session.spectra = spectra
        new_specxplore_session.initialize_specxplore_session()
        with open(filepath, "wb") as file:
            pickle.dump(new_specxplore_session, file)
        return None
    

    def save_pairwise_similarity_matrices_to_file(
            self, 
            run_name : str, 
            directory_path : str
            ) -> None:
        """ Saves the three similarity matrices to file with a run_name prefix to the specified directory. The output 
        format is a .npy object that can be loaded using numpy.load.
        """
        np.save(
            os.path.join(directory_path, run_name, "ms2ds.npy"), 
            self.scores_ms2deepscore, 
            allow_pickle=False
        )
        np.save(
            os.path.join(directory_path, run_name, "modcos.npy"), 
            self.scores_modified_cosine, 
            allow_pickle=False
        )
        np.save(
            os.path.join(directory_path, run_name, "s2v.npy"), 
            self.scores_spec2vec, 
            allow_pickle=False
        )
        return None
    
    def scale_coordinate_system(self, scaler : float):
        """ Applies scaling to coordinate system in tsne_coordinates_table """

        assert not np.isclose([scaler], [0], rtol=1e-05, atol=1e-08, equal_nan=False)[0], (
            'Scaling with 0 or near 0 not allowed; likely loss of data!'
        )
        self.tsne_coordinates_table["x"] = utils.scale_array_to_minus1_plus1(
             self.tsne_coordinates_table["x"].to_numpy()
             ) * scaler
        self.tsne_coordinates_table["y"] = utils.scale_array_to_minus1_plus1(
             self.tsne_coordinates_table["y"].to_numpy()
             ) * scaler


def convert_matchms_spectra_to_specxplore_spectra(
        spectra = List[matchms.Spectrum]
        ) -> List[Spectrum]:
    """ Converts list of matchms.Spectrum objects to list of specxplore_data.Spectrum objects. """
    spectra_converted = [
        Spectrum(
            mass_to_charge_ratios = spec.peaks.mz, 
            precursor_mass_to_charge_ratio = float(spec.get("precursor_mz")), 
            spectrum_iloc = idx, 
            intensities = spec.peaks.intensities, 
            feature_id=spec.get("feature_id")    
        ) 
        for idx, spec 
        in enumerate(spectra)
    ]
    return spectra_converted


def construct_init_table(spectra : List[Spectrum]) -> pd.DataFrame:
    ''' Creates initialized table for metadata or classification in specXplore. Table is a pandas.DataFrame with
    string and int columns indicating the feature_id, and spectrum_iloc.
    
    Parameters
        spectra: alist of matchms.spectrum objects. These should contain spectra with unique feature_ids.

    Returns
        init_table: a pandas.DataFrame with two columns: a string column for feature_id, and a int column for 
        spectrum_iloc.
    '''

    spectrum_ilocs = [spec.spectrum_iloc for spec in spectra]
    feature_ids = [spec.feature_id for spec in spectra] 

    assert spectrum_ilocs == [iloc for iloc in range(0, len(spectra))], (
        "spectrum iloc must equal sequence from 0 to number of spectra"
    )
    init_table = pd.DataFrame(
        data = {
            "feature_id" : feature_ids, 
            "spectrum_iloc" : spectrum_ilocs
        }
    )
    init_table["feature_id"] = init_table["feature_id"].astype("string")
    return init_table


def load_specxplore_object_from_pickle(filepath : str) -> session_data:
    with open(filepath, 'rb') as file:
        specxplore_object = pickle.load(file) 
    assert isinstance(specxplore_object, session_data), (
        'Provided data must be a session_data object!'
    )
    return specxplore_object


def filter_spectrum_top_k_intensity_fragments(
        input_spectrum : Spectrum, 
        k : int
        ) -> Spectrum:
    """ Filter unbinned Spectrum object to top-K highest intensity fragments for display in fragmap. """

    assert k >= 1, 'k must be larger or equal to one.'
    assert input_spectrum.is_binned_spectrum == False, (
        "filter_spectrum_top_k_intensity_fragments() requires unbinned spectrum."
    )
    spectrum = copy.deepcopy(input_spectrum)
    if spectrum.intensities.size > k:
        index_of_k_largest_intensities = np.argpartition(spectrum.intensities, -k)[-k:]
        mass_to_charge_ratios = spectrum.mass_to_charge_ratios[index_of_k_largest_intensities]
        intensities = spectrum.intensities[index_of_k_largest_intensities]
        spectrum = Spectrum(
            mass_to_charge_ratios = mass_to_charge_ratios, 
            precursor_mass_to_charge_ratio = spectrum.precursor_mass_to_charge_ratio,
            spectrum_iloc = spectrum.spectrum_iloc, 
            feature_id = spectrum.feature_id, 
            intensities = intensities
        )
    return(spectrum)


@dataclass(frozen=True)
class SpectraDF:
    """ 
    Dataclass container for long format data frame containing multiple spectra.

    Parameters:
        data: A pandas.DataFrame with columns ('spectrum_identifier', 'mass_to_charge_ratio', 'intensity', 
        'mass_to_charge_ratio_aggregate_list', 'intensity_aggregate_list', 'is_neutral_loss', 'is_binned_spectrum') 
        of types (np.int64, np.double, np.double, object, object, bool, bool). For both aggregate_list columns the 
        expected input is a List[List[np.double]].
    Methods:
        get_data(): Returnsa copy of data frame object stored in SpectraDF instance.
        get_column_as_np(): Returns a copy of a specific column from SpectraDF as numpy array.

    Developer Note: 
        Requires assert_column_set and assert_column_types functions.
        The data dataframe elements are still mutable, frozen only prevent overwriting the object as a whole. Accidental
        modification can be prevented by using the get_data() method and avoiding my_SpectraDF._data accessing.
    """
    _data: pd.DataFrame
    _expected_columns : Tuple = field(
        default=('spectrum_identifier', 'mass_to_charge_ratio', 'intensity', 'mass_to_charge_ratio_aggregate_list', 
            'intensity_aggregate_list', 'is_neutral_loss', 'is_binned_spectrum'), 
        compare = False, hash = False, repr=False)
    _expected_column_types : Tuple = field(
        default=(np.int64, np.double, np.double, object, object, bool, bool), 
        compare = False, hash = False, repr=False )    
    

    def __post_init__(self):
        """ Assert that data provided to constructor is valid. """

        assert isinstance(self._data, pd.DataFrame), "Data must be a pandas.DataFrame"
        expected_column_types = dict(
            zip(
                self._expected_columns, 
                self._expected_column_types
            )
        )
        assert_column_set(self._data.columns.to_list(), self._expected_columns)
        assert_column_types(self._data.dtypes.to_dict(), expected_column_types)


    def get_data(self):
        """ Return a copy of the data frame object stored in SpectraDF instance. """

        return copy.deepcopy(self._data)
    

    def get_column_as_np(self, column_name):
        """ Return a copy of a specific column from SpectraDF as numpy array. """

        assert column_name in self._expected_columns, ( 
            f"Column {column_name} not a member of SpectraDF data frame."
        )
        array = self._data[column_name].to_numpy(copy=True)
        return array


def assert_column_types(type_dict_provided , type_dict_expected) -> None:
    """ 
    Assert types for keys in type_dict match those for key in expected.

    Parameters:
        type_dict_provided: Dict with key-value pairs containing derived column name (str) and column type (type).
        type_dict_expected: Dict with key-value pairs containing expected column name (str) and column type (type).
    Returns:
        None
    Raises:
        ValueError: if types do not match in provided dictionaries.
    """
    for key in type_dict_provided:
        assert type_dict_provided[key] == type_dict_expected[key], (
            f"Provided dtype for column {key} is {type_dict_provided[key]},"
            f" but requires {type_dict_expected[key]}"
        )
    return None


def assert_column_set(columns_provided : List[str], columns_expected : List[str]) -> None:
    """
    Check if provided columns match with expected columns.

    Parameters:
        columns_provided: List[str] of column names (columns derived from pd.DataFrame).
        columns_expected: List[str] of column names (columns expected for pd.DataFrame).
    Returns:
        None.
    Raises:
        ValueError: if column sets provided don't match.
    """

    set_provided = set(columns_provided)
    set_expected = set(columns_expected)
    assert set_provided == set_expected, ("Initialization error, provided columns do not match expected set.")
    return None


def run_tsne_grid(
        distance_matrix : np.ndarray,
        perplexity_values : List[int], 
        random_states : Union[List, None] = None
        ) -> List[TsneGridEntry]:
    """ Runs t-SNE embedding routine for every provided perplexity value in perplexity_values list.

    Parameters:
        distance_matrix: An np.ndarray containing pairwise distances.
        perplexity_values: A list of perplexity values to try for t-SNE embedding.
        random_states: None or a list of integers specifying the random state to use for each k-medoid run.
    Returns: 
        A list of TsneGridEntry objects containing grid results. 
    """

    if random_states is None:
        random_states = [ 0 for _ in perplexity_values ]
    output_list = []
    for idx, perplexity in enumerate(perplexity_values):
        model = TSNE(
            metric="precomputed", 
            random_state = random_states[idx], 
            init = "random", 
            perplexity = perplexity
        )
        z = model.fit_transform(distance_matrix)
        
        # Compute embedding quality
        dist_tsne = squareform(pdist(z, 'seuclidean'))
        spearman_score = np.array(spearmanr(distance_matrix.flat, dist_tsne.flat))[0]
        pearson_score = np.array(pearsonr(distance_matrix.flat, dist_tsne.flat))[0]
        output_list.append(
            TsneGridEntry(
                perplexity, 
                z[:,0], 
                z[:,1], 
                pearson_score, 
                spearman_score, 
                random_states[idx]
            )
        )
    return output_list


def render_tsne_fitting_results_in_browser(tsne_list : List[TsneGridEntry]) -> None:
    """ Plots pearson and spearman scores vs perplexity for each entry in list of TsneGridEntry objects. """
    
    pearson_scores = [x.spearman_score for x in tsne_list]
    spearman_scores = [x.pearson_score for x in tsne_list]
    perplexities = [x.perplexity for x in tsne_list]

    trace_spearman = go.Scatter(x = perplexities, y = spearman_scores, name="spearman_score", mode = "markers")
    trace_pearson = go.Scatter(x = perplexities, y = pearson_scores, name="pearson_score", mode = "markers")
    fig = go.Figure([trace_pearson, trace_spearman])
    fig.update_layout(xaxis_title="Perplexity", yaxis_title="Score")
    fig.show(renderer = "browser")
    return None


def convert_similarity_to_distance(similarity_matrix : np.ndarray) -> np.ndarray:
    """ 
    Converts pairwise similarity matrix to distance matrix with values between 0 and 1. Assumes that the input is a
    similarity matrix with values in range 0 to 1 up to floating point error.

    Developer Note:
        spec2vec scores do not appear to be in this range.
    """

    distance_matrix = 1.- similarity_matrix
    distance_matrix = np.round(distance_matrix, 6) # Round to deal with floating point issues
    distance_matrix = np.clip(distance_matrix, a_min = 0, a_max = 1) # Clip to deal with floating point issues
    return distance_matrix


def run_kmedoid_grid(
        distance_matrix : np.ndarray, 
        k_values : List[int], 
        random_states : Union[List, None] = None
        ) -> List[KmedoidGridEntry]:
    """ Runs k-medoid clustering for every value in k_values. 
    
    Parameters:
        distance_matrix: An np.ndarray containing pairwise distances.
        k_values: A list of k values to try in k-medoid clustering.
        random_states: None or a list of integers specifying the random state to use for each k-medoid run.
    Returns: 
        A list of KmedoidGridEntry objects containing grid results.
    """

    if random_states is None:
        random_states = [ 0 for _ in k_values ]
    output_list = []
    for k in k_values:
        assert isinstance(k, int), (
            "k must be python int object. KMedoids module requires strict Python int object (np.int64 rejected!)"
        )
    for idx, k in enumerate(k_values):
        cluster = KMedoids(
            n_clusters=k, 
            metric='precomputed', 
            random_state=random_states[idx], 
            method = "fasterpam"
        )  
        cluster_assignments = cluster.fit_predict(distance_matrix)
        cluster_assignments_strings = [
            "km_" + str(elem) 
            for elem in cluster_assignments
        ]
        score = silhouette_score(
            X = distance_matrix, 
            labels = cluster_assignments_strings, 
            metric= "precomputed"
        )
        output_list.append(
            KmedoidGridEntry(
                k, 
                cluster_assignments_strings, 
                score, 
                random_states[idx]
            )
        )
    return output_list


def render_kmedoid_fitting_results_in_browser(
        kmedoid_list : List[KmedoidGridEntry]
        ) -> None:
    """ Plots Silhouette Score vs k for each entry in list of KmedoidGridEntry objects. """
    scores = [x.silhouette_score for x in kmedoid_list]
    ks = [x.k for x in kmedoid_list]
    fig = plotly.express.scatter(x = ks, y = scores)
    fig.update_layout(
        xaxis_title="K (Number of Clusters)", 
        yaxis_title="Silhouette Score"
    )
    fig.show(renderer = "browser")
    return None


def print_kmedoid_grid(grid : List[KmedoidGridEntry]) -> None:
    """ Prints all values in kmedoid grid in readable format. """

    print("iloc Number-of-Clusters Silhouette-Score")
    for iloc, elem in enumerate(grid):
        print(iloc, elem.k, round(elem.silhouette_score, 3))
    return None


def print_tsne_grid(grid : List[TsneGridEntry]) -> None:   
    """ Prints all values in tsne grid in readable format. """

    print('iloc Perplexity Pearson-score Spearman-score')
    for iloc, elem in enumerate(grid):
        print(iloc, elem.perplexity, round(elem.pearson_score, 3), round(elem.spearman_score, 3))


def attach_columns_via_feature_id(init_table : pd.DataFrame, addon_data : pd.DataFrame,) -> pd.DataFrame:
    """ Attaches addon_data to data frame via join on 'feature_id'. 
    
    The data frame can be a class table or metadata table and is assumed to be derived from the construct_init_table() 
    and contain feature_id and spectrum_iloc columns.
    
    Input
        init_table: pandas.DataFrame object with at least a feature_id column (type string)
        addon_data: pandas.DataFrame object with a feature_id column and additional columns to be merged into metadata. 
            Columns can be of any type.
    Output: 
        extended_init_table: pandas.DataFrame with feature_id column and additional columns from addon_data. Any NA values
            produced are replaced with strings that read: "not available". Any entries are converted to string.
    """

    assert "feature_id" in init_table.columns, "feature_id column must be available in metadata"
    assert "feature_id" in addon_data.columns, "feature_id column must be available in addon_data"
    assert (init_table["feature_id"].dtype 
            == addon_data["feature_id"].dtype 
            == 'string'), (
        "feature_id column must be of the same type."
    )
    extended_init_table = copy.deepcopy(init_table)
    extended_init_table = extended_init_table.merge(
        addon_data.loc[:, ~addon_data.columns.isin(['spectrum_iloc'])],
        left_on = "feature_id", 
        right_on = "feature_id", 
        how = "left"
    )
    extended_init_table.reset_index(inplace=True, drop=True)
    extended_init_table = extended_init_table.astype('string')
    extended_init_table = extended_init_table.replace(
        to_replace=np.nan, 
        value = "not available"
    )
    return extended_init_table


def remove_white_space_from_df(input_df : pd.DataFrame) -> pd.DataFrame:
    ''' Removes whitespace from all entries in input_df. 
    
    White space removal is essential for accurate chemical classification parsing in node highlighting of specXplore.
    '''
    output_df = copy.deepcopy(input_df)
    output_df = input_df.replace(to_replace=" ", value = "_", regex=True)
    return output_df


# Named Tuple Basis for ClassificationEntry class
_ClassificationEntry = namedtuple(
    "ClassificationEntry", 
    field_names=[
        'inchi', 'smiles', 'cf_kingdom', 'cf_superclass', 'cf_class', 'cf_subclass', 'cf_direct_parent', 
        'npc_class', 'npc_superclass', 'npc_pathway', 'npc_isglycoside'],
    defaults = ["Not Available" for _ in range(0, 11)])

class ClassificationEntry(_ClassificationEntry):
    """ 
    Tuple container class for classification entries. 

    Parameters:
        inchi: Compound inchi string.
        smiles: Compound smiles str
        cf_kingdom: ClassyFire kingdom classification.
        cf_superclass: ClassyFire superclass classification.
        cf_class: ClassyFire class classification.
        cf_subclass: ClassyFire subclass classification.
        cf_direct_parent: ClassyFire direct_parent classification.
        npc_class: NPClassifier class classification.
        npc_superclass: NPClassifier superclass classification.
        npc_pathway: NPClassifier pathway classification.
        npc_isglycoside: NPClassifier isglycoside classification.
    """
    _slots_ = ()




def initialize_classification_output_file(filepath) -> None:
    """ Creates csv file with ClassificationEntry headers if not exists at filepath. """
    # Initialize the file
    if not os.path.isfile(filepath):
        with open(filepath, "w") as file:
            pass
    # Add header line to file
    if os.stat(filepath).st_size == 0:
        with open(filepath, "a") as file: # a for append mode
            file.write(", ".join(ClassificationEntry._fields) + os.linesep)
    return None

def append_classes_to_file(classes : ClassificationEntry, filepath : str) -> None:
    """ Appends classification entry data to file. """
    pandas_row = pd.DataFrame([classes])
    pandas_row.to_csv(filepath, mode='a', header=False, sep = ",", na_rep="Not Available", index = False)
    return None

def batch_run_get_classes(
        inchi_list : List[str], 
        filepath : str, 
        verbose : bool = True) -> pd.DataFrame:
    """ 
    Function queries GNPS API for NPClassifier and ClassyFire classifications for all inchi list. 
    
    A pandas.DataFrame is returned as output, and the corresponding csv is saved to file iteratively. This is done to
    allow run continuation in case of API disconnect errors.
    
    Parameters:
        inchi_list: List of inchi strings.
        filename: str file path for output to be saved to iteratively.
        verbose: Boolean indicator that controls progress prints. Default is true. Deactive prints by setting to False.
    
    Returns:
        A pandas.DataFrame constructed from ClassificationEntry tuples. In addition, the list index is added as 
        "iloc_spectrum_identifier" column.

        Also saves intermediate results to csv file.
    """
    classes_list = []
    initialize_classification_output_file(filepath)
    for iloc, inchi in enumerate(inchi_list):
        if verbose and (iloc+1) % 10 == 0 and not iloc == 0:
            print(f"{iloc + 1} spectra done, {len(inchi_list) - (iloc+1)} spectra remaining.")
        classes = get_classes(inchi)
        append_classes_to_file(classes, filepath)
        classes_list.append(classes)
    classes_df = pd.DataFrame.from_records(classes_list, columns=ClassificationEntry._fields)
    classes_df["iloc_spectrum_identifier"] = classes_df.index
    return classes_df

def get_classes(inchi: Union[str, None]) -> ClassificationEntry:
    """
    Function returns cf (classyfire) and npc (natural product classifier) classes for a provided inchi.
    
    Parameters
        inchi: A valid inchi for which class information should be fetched. An input of "" or None is handled as an 
               exception with a dict of "Not Available" data being returned.
    Returns:
        ClassificationEntry named tuple with classification information if available. If classification retrieval fails,
        ClassificationEntry will contain "Not Available" defaults. "Not Available" defaults may also be produced by
        server disconnections while in principle the classification may be obtainable.
    """
    if inchi is None or inchi == "":
        print("No inchi, returning Not Available structure.")
        return ClassificationEntry()
    smiles = matchms.utils.convert_inchi_to_smiles(inchi) # OLD matchms syntax
    #smiles = matchms.metadata_utils.convert_inchi_to_smiles(inchi) # NEW matchms syntax
    
    # Get ClassyFire classifications
    safe_smiles = urllib.parse.quote(smiles)  # url encoding
    try:
        cf_result = get_cf_classes(safe_smiles, inchi)
    except:
        cf_result = None
    if not cf_result:
        cf_result = ["Not Available" for _ in range(5)]

    # Get NPClassifier classifications
    try:
        npc_result = get_npc_classes(safe_smiles)
    except:
        npc_result = None
    if not npc_result:
        npc_result = ["Not Available" for _ in range(4)]
        
    output = ClassificationEntry(
        inchi= inchi, smiles=safe_smiles, cf_kingdom=cf_result[0], cf_superclass=cf_result[1], cf_class=cf_result[2],
        cf_subclass=cf_result[3], cf_direct_parent=cf_result[4], npc_class=npc_result[0], npc_superclass=npc_result[1],
        npc_pathway=npc_result[2], npc_isglycoside=npc_result[3])
    return output

def do_url_request(url: str, sleep_time_seconds : int = 2) -> Union[bytes, None]:
    """ 
    Perform url request and return bytes from .read() or None if HTTPError is raised.

    Parameters:
        url: url string that should be accessed.
        sleep_time_seconds: integer value indicating the number of seconds to wait in between API requests.
    :param url: url to access
    :return: open file or None if request failed
    """
    time.sleep(sleep_time_seconds) # Added to prevent API overloading.
    try:
        with urllib.request.urlopen(url) as inf:
            result = inf.read()
    except (urllib.error.HTTPError, urllib.error.URLError): # request fail => None result
        result = None
    return result

def read_list_from_text(filename : str) -> List[str]:
    """ Reads newline separated file into list. """
    with open(filename) as f:
        output_list = f.read().splitlines()
    return output_list

def get_json_cf_results(raw_json: bytes) -> List[str]:
    """ 
    Extracts ClassyFire classification key data in order from bytes version of json string.
    
    Names of the keys extracted in order are: ['kingdom', 'superclass', 'class', 'subclass', 'direct_parent']
    List elements are concatenated with '; '.

    :param raw_json: Json str as a bytes object containing ClassyFire information
    :return:List of extracted ClassyFire class assignment strings.
    """
    cf_results_list = []
    json_string = json.loads(raw_json)
    key_list = ['kingdom', 'superclass', 'class', 'subclass', 'direct_parent']
    for key in key_list:
        data_dict = json_string.get(key, "")
        data_string = ""
        if data_dict:
            data_string = data_dict.get('name', "")
        cf_results_list.append(data_string)
    return cf_results_list



def get_json_npc_results(raw_json: bytes) -> List[str]:
    """ Extracts NPClassifier classification key data in order from bytes version of json string.
    
    Names of the keys extracted in order are: class_results, superclass_results, pathway_results, isglycoside.
    List elements are concatenated with '; '.

    :param raw_json: Json str as a bytes object containing NPClassifier information.
    :return: List of extracted NPClassifier class assignment strings.
    """
    npc_results_list = []
    json_string = json.loads(raw_json)
    # Key list extraction
    key_list = ["class_results", "superclass_results", "pathway_results"]
    for key in key_list:
        data_list = json_string.get(key, "")
        data_string = ""
        if data_list:
            data_string = "; ".join(data_list)
        npc_results_list.append(data_string)
    # Boolean key special extraction
    last_key = "isglycoside" # requires special treatment since boolean
    data_last = json_string.get(last_key, "")
    last_string = "0"
    if data_last:
        last_string = "1"
    npc_results_list.append(last_string)
    return npc_results_list



def get_cf_classes(smiles: str, inchi: str) -> Union[None, List[str]]:
    """ Get ClassyFire classes through GNPS API.

    :param smiles: Smiles for the query spectrum
    :param inchi: Inchikey for the query spectrum

    :return: List of strings with ClassyFire classes if provided by GNPS api ['cf_kingdom' 'cf_superclass' 'cf_class' 
        'cf_subclass' 'cf_direct_parent'], or None. 
    """
    classes_list = None
    if smiles is not None:
        cf_url_base_smiles = "https://gnps-structure.ucsd.edu/classyfire?smiles="
        cf_url_query_smiles = cf_url_base_smiles + smiles
        smiles_query_result = do_url_request(cf_url_query_smiles)
        if smiles_query_result is not None:
            classes_list = get_json_cf_results(smiles_query_result)
    if classes_list is not None: # do only if smiles query not successful.
        if inchi is not None:
            cf_url_query_inchi = f"https://gnps-classyfire.ucsd.edu/entities/{inchi}.json"
            inchi_query_result = do_url_request(cf_url_query_inchi)
            if inchi_query_result is not None:
                classes_list = get_json_cf_results(inchi_query_result)
    return classes_list



def get_npc_classes(smiles: str) -> Union[None, List[str]]:
    """ Get NPClassifier classes through GNPS API.

    :param smiles: Smiles for the query spectrum
    :return: List of strings with NPClassifier classes if provided by GNPS api ['npc_class' 'npc_superclass' 
        'npc_pathway' 'npc_isglycoside'], or None. 
    """
    classes_list = None
    if smiles is not None:
        npc_url_base_smiles = "https://npclassifier.ucsd.edu/classify?smiles="
        npc_url_query_smiles = npc_url_base_smiles + smiles
        query_result_json = do_url_request(npc_url_query_smiles)
        if query_result_json is not None:
            classes_list = get_json_npc_results(query_result_json)
    return classes_list



def _return_model_filepath(path : str, model_suffix:str) -> str:
    """ Function parses path input into a model filepath. If a model filepath is provided, it is returned unaltered , if 
    a directory path is provided, the model filepath is searched for and returned.
    
    :param path: File path or directory containing model file with provided model_suffix.
    :param model_suffix: Model file suffix (str)
    :returns: Filepath (str).
    :raises: Error if no model in file directory or filepath does not exist. Error if more than one model in directory.
    """
    filepath = []
    if path.endswith(model_suffix):
        # path provided is a model file, use the provided path
        filepath = path
        assert os.path.exists(filepath), "Provided filepath does not exist!"
    else:
        # path provided is not a model filepath, search for model file in provided directory
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(model_suffix):
                    filepath.append(os.path.join(root, file))
        assert len(filepath) > 0, f"No model file found in given path with suffix '{model_suffix}'!"
        assert len(filepath) == 1, (
        "More than one possible model file detected in directory! Please provide non-ambiguous model directory or"
        "filepath!")
    return filepath[0]



def compute_similarities_ms2ds(spectrum_list:List[matchms.Spectrum], model_path:str) -> np.ndarray:
    """ Function computes pairwise similarity matrix for list of spectra using pretrained ms2deepscore model.
    
    Parameters
        spectrum_list: List of matchms ms/ms spectra. These should be pre-processed and must incldue peaks.
        model_path: Location of ms2deepscore pretrained model file path (filename ending in .hdf5 or file-directory)
    Returns: 
        ndarray with shape (n, n) where n is the number of spectra (Pairwise similarity matrix).
    """
    filename = _return_model_filepath(model_path, ".hdf5")
    model = load_model(filename) # Load ms2ds model
    similarity_measure = MS2DeepScore(model)
    scores_matchms = calculate_scores(spectrum_list, spectrum_list, similarity_measure, is_symmetric=True)
    scores_ndarray = scores_matchms.scores
    return scores_ndarray



def compute_similarities_s2v(spectrum_list:List[matchms.Spectrum], model_path:str) -> np.ndarray:
    """ Function computes pairwise similarity matrix for list of spectra using pretrained spec2vec model.
    
    Parameters:
        spectrum_list: List of matchms ms/ms spectra. These should be pre-processed and must incldue peaks.
        model_path: Location of spec2vec pretrained model file path (filename ending in .model or file-directory)
    Returns: 
        ndarray with shape (n, n) where n is the number of spectra (Pairwise similarity matrix).
    """
    filename = _return_model_filepath(model_path, ".model")
    model = gensim.models.Word2Vec.load(filename) # Load s2v model
    similarity_measure = Spec2Vec(model=model)
    scores_matchms = calculate_scores(spectrum_list, spectrum_list, similarity_measure, is_symmetric=True)
    scores_ndarray = scores_matchms.scores
    return scores_ndarray



def compute_similarities_cosine(spectrum_list:List[matchms.Spectrum], cosine_type : str = "ModifiedCosine"):
    """ Function computes pairwise similarity matrix for list of spectra using specified cosine score. 
    
    Parameters:
        spectrum_list: List of matchms ms/ms spectra. These should be pre-processed and must incldue peaks.
        cosine_type: String identifier of supported cosine metric, options: ["ModifiedCosine", "CosineHungarian", 
        "CosineGreedy"]
    Returns:
        ndarray with shape (n, n) where n is the number of spectra (Pairwise similarity matrix).
    """
    valid_types = ["ModifiedCosine", "CosineHungarian", "CosineGreedy"]
    assert cosine_type in valid_types, f"Cosine type specification invalid. Use one of: {str(valid_types)}"
    if cosine_type == "ModifiedCosine":
        similarity_measure = ModifiedCosine()
    elif cosine_type == "CosineHungarian":
        similarity_measure = CosineHungarian()
    elif cosine_type == "CosineGreedy":
        similarity_measure = CosineGreedy()
    tmp = calculate_scores(spectrum_list, spectrum_list, similarity_measure, is_symmetric=True)
    scores = extract_similarity_scores_from_matchms_cosine_array(tmp.scores)
    return scores


def extract_similarity_scores_from_matchms_cosine_array(tuple_array : np.ndarray) -> np.ndarray:
    """ 
    Function extracts similarity matrix from matchms cosine scores array.
    
    The cosine score similarity output of matchms stores output in a numpy array of pair-tuples, where each tuple 
    contains (sim, n_frag_overlap). This function extracts the sim scores, and returns a numpy array corresponding to 
    pairwise similarity matrix.

    Parameters:
        tuple_array: A single matchms spectrum object.
    Returns: 
        A np.ndarray with shape (n, n) where n is the number of spectra deduced from the dimensions of the input
        array. Each element of the ndarray contains the pairwise similarity value.
    """
    sim_data = [ ]
    for row in tuple_array:
        for elem in row:
            sim_data.append(float(elem[0]))
    return(np.array(sim_data).reshape(tuple_array.shape[0], tuple_array.shape[1]))


def extract_molecular_family_assignment_from_graphml(filepath : str) -> pd.DataFrame:
    """ Function extracts molecular family componentindex for each node in gnps mgf export. Expects that each
    spectrum is a feature, hence the clustering option in molecular networking must be deactivated. """
    graph = read_graphml(filepath)
    data = json_graph.node_link_data(graph)
    entries = []
    for node in data['nodes']:
        entry = {"id" : node['id'], "spectrum_id" : node['SpectrumID'], 'molecular_family' : node['componentindex']}
        entries.append(entry)
    df = pd.DataFrame.from_records(entries)
    df['id'] = df['id'].astype(int)
    df['idx'] = df['id'] -1
    df.sort_values(by = "id", inplace=True)
    df.reset_index(drop = True, inplace=True)
    return df

def apply_basic_matchms_filters_to_spectra(
        input_spectra : List[matchms.Spectrum],
        minimum_number_of_peaks_per_spectrum : int = 3,
        maximum_number_of_peaks_per_spectrum : int = 200,
        max_mz = 1000,
        min_mz = 0,
        verbose = True
        ) -> List[matchms.Spectrum]:
    ''' 
    Applies basic pre-processing of spectra required for specXplore processing.     
    '''

    if verbose:
        print("Number of spectra prior to filtering: ", len(input_spectra))
    # Normalize intensities, important for similarity measures!
    output_spectra = copy.deepcopy(input_spectra)
    output_spectra = [matchms.filtering.normalize_intensities(spec) for spec in output_spectra]
    output_spectra = [matchms.filtering.select_by_mz(spec, mz_from = 0, mz_to = 1000) for spec in output_spectra]
    # Clean spectra by remove very low intensity fragments, noise removal
    output_spectra = [
        matchms.filtering.reduce_to_number_of_peaks(
            spec, n_required = minimum_number_of_peaks_per_spectrum, n_max= maximum_number_of_peaks_per_spectrum) 
        for spec in output_spectra]
    # Add precursor mz values to matchms spectrum entry
    output_spectra = [matchms.filtering.add_precursor_mz(spec)  for spec in output_spectra]
    # remove none entries in list (no valid spectrum returned)
    output_spectra = [spec for spec in output_spectra if spec is not None]
    if verbose:
        print("Number of spectra after to filtering: ", len(output_spectra))
    return output_spectra


