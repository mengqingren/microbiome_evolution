import numpy
import sys
import bz2
import os.path 
import stats_utils
from math import floor, ceil

###############################################################################
#
# Set up default source and output directories
#
###############################################################################

data_directory = os.path.expanduser("~/ben_nandita_hmp_data/")
analysis_directory = os.path.expanduser("~/ben_nandita_hmp_analysis/")
scripts_directory = os.path.expanduser("~/ben_nandita_hmp_scripts/")

# We use this one to debug because it was the first one we looked at
debug_species_name = 'Bacteroides_uniformis_57318'

###############################################################################
#
# Methods for parsing sample metadata
#
###############################################################################

###############################################################################
#
# Loads metadata for HMP samples 
# Returns map from subject -> map of samples -> set of accession IDs
#
###############################################################################
def parse_subject_sample_map(): 

    subject_sample_map = {}
    
    # First load HMP metadata
    file = open(scripts_directory+"HMP_ids.txt","r")
    file.readline() # header
    for line in file:
        items = line.split("\t")
        subject_id = items[0].strip()
        sample_id = items[1].strip()
        accession_id = items[2].strip()
        country = items[3].strip()
        continent = items[4].strip()
        
        if subject_id not in subject_sample_map:
            subject_sample_map[subject_id] = {}
            
        if sample_id not in subject_sample_map[subject_id]:
            subject_sample_map[subject_id][sample_id] = set()
            
        subject_sample_map[subject_id][sample_id].add(accession_id)
    file.close()
    
    # Then load Kuleshov data 
    file = open(scripts_directory+"kuleshov_ids.txt","r")
    file.readline() # header
    for line in file:
        items = line.split("\t")
        subject_id = items[0].strip()
        sample_id = items[1].strip()
        accession_id = items[2].strip()
        country = items[3].strip()
        continent = items[4].strip()
        
        if subject_id not in subject_sample_map:
            subject_sample_map[subject_id] = {}
            
        if sample_id not in subject_sample_map[subject_id]:
            subject_sample_map[subject_id][sample_id] = set()
            
        subject_sample_map[subject_id][sample_id].add(accession_id)
    file.close()  
    
    # Repeat for other data
    # Nothing else so far
     
    return subject_sample_map 

###############################################################################
#
# Prunes sample list to remove multiple timepoints from same subject
# Returns len(sampe_list) boolean array with element=False if sample was pruned  
#
###############################################################################
def calculate_unique_samples(subject_sample_map, sample_list=[]):

    if len(sample_list)==0:
        sample_list = list(sorted(flatten_samples(subject_sample_map).keys()))
    
    # invert subject sample map
    sample_subject_map = {}
    for subject in subject_sample_map.keys():
        for sample in subject_sample_map[subject].keys():
            sample_subject_map[sample] = subject
    
    subject_idx_map = {}
        
    for i in xrange(0,len(sample_list)):
        subject = sample_subject_map[sample_list[i]]
        if not subject in subject_idx_map:
            subject_idx_map[subject] = i
            
    unique_idxs = numpy.zeros(len(sample_list),dtype=numpy.bool_)
    for i in subject_idx_map.values():
        unique_idxs[i]=True
    
    return unique_idxs

###############################################################################
#
# For a given list of samples, calculates which belong to different subjects
# which belong to different timepoints in same subject, and which are the same
# timepoint.
#
# Returns same_sample_idxs, same_subject_idxs, diff_subject_idxs, 
# each of which is a tuple with idx1 and idx2. All pairs are included 
# only once. 
#
###############################################################################
def calculate_subject_pairs(subject_sample_map, sample_list=[]):

    if len(sample_list)==0:
        sample_list = list(sorted(flatten_samples(subject_sample_map).keys()))
    
    # invert subject sample map
    sample_subject_map = {}
    for subject in subject_sample_map.keys():
        for sample in subject_sample_map[subject].keys():
            sample_subject_map[sample] = subject
    
    same_sample_idx_lower = []
    same_sample_idx_upper = []
    same_subject_idx_lower = []
    same_subject_idx_upper = []
    diff_subject_idx_lower = []
    diff_subject_idx_upper = []
        
    for i in xrange(0,len(sample_list)):
        same_sample_idx_lower.append(i)
        same_sample_idx_upper.append(i)
        for j in xrange(0,i):
            if sample_subject_map[sample_list[i]]==sample_subject_map[sample_list[j]]:
                same_subject_idx_lower.append(i)
                same_subject_idx_upper.append(j)
            else: 
                diff_subject_idx_lower.append(i)
                diff_subject_idx_upper.append(j)
    
    same_sample_idxs = (numpy.array(same_sample_idx_lower,dtype=numpy.int32), numpy.array(same_sample_idx_upper,dtype=numpy.int32))
    
    same_subject_idxs = (numpy.array(same_subject_idx_lower,dtype=numpy.int32), numpy.array(same_subject_idx_upper,dtype=numpy.int32))
    
    diff_subject_idxs = (numpy.array(diff_subject_idx_lower,dtype=numpy.int32), numpy.array(diff_subject_idx_upper,dtype=numpy.int32))
    
    return same_sample_idxs, same_subject_idxs, diff_subject_idxs


###############################################################################
#
# Returns a flat map of all the replicate sets for
# the samples in subject_sample_map, indexed by sample key        
#
###############################################################################
def flatten_samples(subject_sample_map):
    
    grouping_replicate_map = {}
    for subject in sorted(subject_sample_map.keys()):
        for sample in sorted(subject_sample_map[subject].keys()):
            grouping_replicate_map[sample] = subject_sample_map[subject][sample]
    
    return grouping_replicate_map


###############################################################################
#
# Returns a flat map of the merged replicate sets for each subject, 
# indexed by subject key 
#   
###############################################################################    
def flatten_subjects(subject_sample_map):
    
    grouping_replicate_map = {}
    for subject in sorted(subject_sample_map.keys()):
        merged_replicates = set()
        for sample in subject_sample_map[subject].keys():
            merged_replicates.update(subject_sample_map[subject][sample])
        grouping_replicate_map[subject] = merged_replicates
        
    return grouping_replicate_map


###############################################################################
#
# groupings = ordered list of nonoverlapping sets of sample names
# samples = ordered list of samples
#
# returns: list whose i-th element contains a numpy array of idxs
#          of the items in samples that are present in the ith grouping
#   
###############################################################################       
def calculate_grouping_idxs(groupings, samples):
    
    grouping_idxs = []
    for i in xrange(0,len(groupings)):
    
        idxs = []
        for j in xrange(0,len(samples)):
            if samples[j] in groupings[i]:
                idxs.append(j)
        idxs = numpy.array(idxs,dtype=numpy.int32)
        #print idxs
        grouping_idxs.append(idxs)
    
    return grouping_idxs


###############################################################################
#
# Methods for parsing species metadata
#
###############################################################################

#############
#
# Returns a list of all species that MIDAS called SNPS for
#
#############
def parse_species_list():
    
    species_names = []
    
    file = open(data_directory+"snps/species_snps.txt","r")
    for line in file:
        species_names.append(line.strip())
    file.close()
    
    return species_names

#############
#
# Returns a list of all species that MIDAS called SNPS for
# sorted in order of decreasing total sequencing depth
#
#############
def parse_depth_sorted_species_list():
    species_coverage_matrix, samples, species = parse_global_marker_gene_coverages()
    return species


#############
#
# Returns a list of all species that MIDAS called SNPS for
# that passed a certain depth / prevalence requirement,
# again sorted in order of decreasing total sequencing depth
#
#############
def parse_good_species_list(min_marker_coverage=5, min_prevalence=10):
    good_species_list = []
    
    species_coverage_matrix, samples, species = parse_global_marker_gene_coverages()
    for i in xrange(0,len(species)):
        
        species_coverages = species_coverage_matrix[i,:]
        if (species_coverages>=min_marker_coverage).sum() >= min_prevalence:
            good_species_list.append(species[i])
    
    return good_species_list

    
    
    
###############################################################################
#
# Methods for parsing coverage of different species across samples
#
###############################################################################

###############################################################################
#
# Loads marker gene coverages produced by MIDAS
# for all species in which SNPs were called 
#
# Returns: species-by-sample matrix of marker gene coverages,
#          with species sorted in descending order of total coverage;
#          ordered list of sample ids; ordered list of species names;
#
###############################################################################
def parse_global_marker_gene_coverages():

    desired_species_names = set(parse_species_list())

    file = bz2.BZ2File("%sspecies/coverage.txt.bz2" %  (data_directory),"r")
    line = file.readline() # header
    samples = line.split()[1:]
    species = []
    species_coverage_matrix = []
    for line in file:
        items = line.split()
        species_name = items[0]
        #print items
        coverages = numpy.array([float(item) for item in items[1:]])
        
        if species_name in desired_species_names:
            species.append(species_name)
            species_coverage_matrix.append(coverages)
    
    file.close()    
    species, species_coverage_matrix = zip(*sorted(zip(species, species_coverage_matrix), key=lambda pair: pair[1].sum(), reverse=True))
    
    species_coverage_matrix = numpy.array(species_coverage_matrix)
    return species_coverage_matrix, samples, species


def parse_gene_coverages(desired_species_name):

    coverage_file = bz2.BZ2File("%ssnps/%s/gene_coverage.txt.bz2" % (data_directory, desired_species_name))

    line = coverage_file.readline() # header
    items = line.split()
    samples = items[1:]
    gene_coverages = {}
    
    for line in coverage_file:
        items = line.split()
        gene_name = items[0]
        depths = numpy.array([float(item) for item in items[1:]])
        
        gene_coverages[gene_name] = depths
        
    return gene_coverages, samples

def parse_coverage_distribution(desired_species_name):

    coverage_distribution_file = bz2.BZ2File("%ssnps/%s/coverage_distribution.txt.bz2" % (data_directory, desired_species_name))

    line = coverage_distribution_file.readline() # header
    samples = []
    sample_coverage_histograms = []
    for line in coverage_distribution_file:
        items = line.split()
        sample_coverage_histogram = {}
        for item in items[1:]:
            subitems = item.split(",")
            sample_coverage_histogram[float(subitems[0])] = float(subitems[1])
        sample_coverage_histograms.append(sample_coverage_histogram)
        samples.append(items[0])
        
    return sample_coverage_histograms, samples
    
## 
# 
# Loads species-specific marker gene coverage
#
##
def parse_marker_gene_coverages(desired_species_name):
    
    marker_file = bz2.BZ2File("%ssnps/%s/marker_coverage.txt.bz2" % (data_directory, desired_species_name))
    
    line = marker_file.readline() # header
    samples = line.split()[1:]
    species = []
    species_coverage_matrix = []
    
    for line in marker_file:
        items = line.split()
        species_name = items[0]
        coverages = numpy.array([float(item) for item in items[1:]])
        species.append(species_name)
        species_coverage_matrix.append(coverages)
    
    marker_file.close()    
    
    species_coverage_matrix = numpy.array(species_coverage_matrix)
    return species_coverage_matrix, samples, species


################
#
# Methods for determining whether samples or sites pass certain depth requirements
#
################
  

def calculate_relative_depth_threshold_map(sample_coverage_histograms, samples, min_nonzero_median_coverage=5, lower_factor=0.5, upper_factor=2):
    
    # returns map of sample name: coverage threshold
    # essentially filtering out samples whose marker depth coverage
    # does not exceed the average coverage threshold
    
    depth_threshold_map = {}
    for i in xrange(0,len(samples)):
        
        # Check if coverage distribution meets certain requirements
        is_bad_coverage_distribution = False
        
        # First check if passes median coverage requirement
        nonzero_median_coverage = stats_utils.calculate_nonzero_median_from_histogram(sample_coverage_histograms[i])
        if round(nonzero_median_coverage) < min_nonzero_median_coverage:
            is_bad_coverage_distribution=True
    
        # Passed median coverage requirement
        # Now check whether a significant number of sites fall between lower and upper factor. 
        lower_depth_threshold = floor(nonzero_median_coverage*lower_factor)-0.5
        upper_depth_threshold = ceil(nonzero_median_coverage*upper_factor)+0.5
    
        depths, depth_CDF = stats_utils.calculate_CDF_from_histogram(sample_coverage_histograms[i])
        # remove zeros
        if depths[0]<0.5:
            depth_CDF -= depth_CDF[0]
            depth_CDF /= depth_CDF[-1]
        
        fraction_in_good_range = depth_CDF[(depths>lower_depth_threshold)*(depths<upper_depth_threshold)].sum()
    
        if fraction_in_good_range < 0.6:
            is_bad_coverage_distribution=True
            
        if is_bad_coverage_distribution:
            lower_depth_threshold = 1000000001
            upper_depth_threshold = 1000000001
        
        depth_threshold_map[samples[i]] = (lower_depth_threshold, upper_depth_threshold)
        
    return depth_threshold_map


def calculate_absolute_depth_threshold_map(species_coverage_vector, samples, avg_depth_threshold=20, site_depth_threshold=15):
    
    # returns map of sample name: coverage threshold
    # essentially filtering out samples whose marker depth coverage
    # does not exceed the average coverage threshold
    
    depth_threshold_map = {}
    for i in xrange(0,len(samples)):
        
        if species_coverage_vector[i]<avg_depth_threshold:    
            lower_depth_threshold=1000000001
        else:
            lower_depth_threshold=site_depth_threshold
    
        upper_depth_threshold = 1000000001
        depth_threshold_map[samples[i]] = (lower_depth_threshold, upper_depth_threshold)
        
    return depth_threshold_map
  

###############################################################################
#
# Reads midas output and prints to stdout in a format 
# suitable for further downstream processing
#
# In the process, filters sites that fail to meet the depth requirements
#
###############################################################################
def pipe_snps(species_name, min_nonzero_median_coverage=5, lower_factor=0.5, upper_factor=2, debug=False):
    
    
    # Load genomic coverage distributions
    sample_coverage_histograms, sample_list = parse_coverage_distribution(species_name)
    depth_threshold_map = calculate_relative_depth_threshold_map(sample_coverage_histograms, sample_list, min_nonzero_median_coverage, lower_factor, upper_factor)
    
   
    # Open MIDAS output files
    ref_freq_file = bz2.BZ2File("%ssnps/%s/snps_ref_freq.txt.bz2" % (data_directory, species_name),"r")
    depth_file = bz2.BZ2File("%ssnps/%s/snps_depth.txt.bz2" % (data_directory, species_name),"r")
    alt_allele_file = bz2.BZ2File("%ssnps/%s/snps_alt_allele.txt.bz2" % (data_directory, species_name),"r")
    info_file = bz2.BZ2File("%ssnps/%s/snps_info.txt.bz2" % (data_directory, species_name),"r")
    marker_file = bz2.BZ2File("%ssnps/%s/marker_coverage.txt.bz2" % (data_directory, species_name))
    
    # get header lines from each file
    depth_line = depth_file.readline()
    ref_freq_line = ref_freq_file.readline()
    alt_line = alt_allele_file.readline()
    info_line = info_file.readline()
    marker_line = marker_file.readline()
    
    # get list of samples
    depth_items = depth_line.split()
    samples = numpy.array(depth_items[1:])
    
    # create depth threshold vector from depth threshold map
    lower_depth_threshold_vector = []
    upper_depth_threshold_vector = []
    for sample in samples:
        lower_depth_threshold_vector.append(depth_threshold_map[sample][0])
        upper_depth_threshold_vector.append(depth_threshold_map[sample][1])
        
    lower_depth_threshold_vector = numpy.array(lower_depth_threshold_vector)
    upper_depth_threshold_vector = numpy.array(upper_depth_threshold_vector)
    
    # Figure out which samples passed our avg_depth_threshold
    passed_samples = (lower_depth_threshold_vector<1e09)
    total_passed_samples = passed_samples.sum()
    
    # Let's focus on those from now on
    samples = list(samples[passed_samples])
    lower_depth_threshold_vector = lower_depth_threshold_vector[passed_samples]
    upper_depth_threshold_vector = upper_depth_threshold_vector[passed_samples]
    
    #print lower_depth_threshold_vector
    
    # print header
    print_str = "\t".join(["site_id"]+samples)
    print print_str
    
    # Only going to look at 1D, 2D, 3D, and 4D sites
    # (we will restrict to 1D and 4D downstream
    allowed_variant_types = set(['1D','2D','3D','4D'])
    
    allele_counts_syn = [] # alt and reference allele counts at 4D synonymous sites with snps
    locations_syn = [] # genomic location of 4D synonymous sites with snps
    genes_syn = [] # gene name of 4D synonymous sites with snps
    passed_sites_syn = numpy.zeros(len(samples))*1.0
    
    allele_counts_non = [] # alt and reference allele counts at 1D nonsynonymous sites with snps
    locations_non = [] # genomic location of 1D nonsynonymous sites
    genes_non = [] # gene name of 1D nonsynonymous sites with snps
    passed_sites_non = numpy.zeros_like(passed_sites_syn)
    
    num_sites_processed = 0
    while True:
            
        # load next lines
        depth_line = depth_file.readline()
        ref_freq_line = ref_freq_file.readline()
        alt_line = alt_allele_file.readline()
        info_line = info_file.readline()
        
        # quit if file has ended
        if depth_line=="":
            break
        
        # parse site info
        info_items = info_line.split()
        variant_type = info_items[5]
        
        # make sure it is either a 1D or 4D site
        if not variant_type in allowed_variant_types:
            continue
    
        # continue parsing site info
        gene_name = info_items[6]
        site_id_items = info_items[0].split("|")
        contig = site_id_items[0]
        location = site_id_items[1]
        new_site_id_str = "|".join([contig, location, gene_name, variant_type])
        
        
    
        # now parse allele count info
        depths = numpy.array([float(item) for item in depth_line.split()[1:]])[passed_samples]
        ref_freqs = numpy.array([float(item) for item in ref_freq_line.split()[1:]])[passed_samples]
        refs = numpy.round(ref_freqs*depths)   
        alts = depths-refs
        
        passed_sites = (depths>=lower_depth_threshold_vector)*1.0
        passed_sites *= (depths<=upper_depth_threshold_vector)
        
        #print passed_sites.sum(), total_passed_samples, passed_sites.sum()/total_passed_samples
        
        # make sure the site is prevalent in enough samples to count as "core"
        if (passed_sites).sum()*1.0/total_passed_samples < 0.5:
            continue
            #passed_sites *= 0
            
        refs = refs*passed_sites
        alts = alts*passed_sites
        depths = depths*passed_sites
        
        total_alts = alts.sum()
        total_refs = depths.sum()
        total_depths = total_alts+total_refs
        
        
        # polarize SNP based on consensus in entire dataset
        if total_alts>total_refs:
            alts,refs = refs,alts
            total_alts, total_refs = total_refs, total_alts
        
        # print string
        read_strs = ["%g,%g" % (A,A+R) for A,R in zip(alts, refs)]
        print_str = "\t".join([new_site_id_str]+read_strs)
        
        print print_str
        #print total_alts
        
        num_sites_processed+=1
        if num_sites_processed%10000==0:
            #sys.stderr.write("%dk sites processed...\n" % (num_sites_processed/1000))   
            if debug:
                break
    
    ref_freq_file.close()
    depth_file.close()
    alt_allele_file.close()
    info_file.close()
    
    # returns nothing

###############################################################################
#
# Loads list of SNPs and counts of target sites from annotated SNPs file
#
# returns (lots of things, see below)
#
###############################################################################
def parse_snps(species_name, debug=False):
    
    # Open post-processed MIDAS output
    snp_file =  bz2.BZ2File("%ssnps/%s/annotated_snps.txt.bz2" % (data_directory, species_name),"r")
    
    line = snp_file.readline() # header
    items = line.split()
    samples = items[1:]
    # Only going to look at 1D and 4D sites
    allowed_variant_types = set(['1D','4D'])
    
    allele_counts_map = {}
    
    # map from gene_name -> var_type -> (list of locations, matrix of allele counts)
    passed_sites_map = {}
    # map from gene_name -> var_type -> (location, sample x sample matrix of whether both samples can be called at that site)
    
    
    num_sites_processed = 0
    for line in snp_file:
        
        items = line.split()
        # Load information about site
        info_items = items[0].split("|")
        chromosome = info_items[0]
        location = long(info_items[1])
        gene_name = info_items[2]
        variant_type = info_items[3]
        pvalue = float(info_items[4])
        
        # make sure it is either a 1D or 4D site
        # (shouldn't be needed anymore)
        if not variant_type in allowed_variant_types:
            continue
        
        # Load alt and depth counts
        alts = []
        depths = []
        for item in items[1:]:
            subitems = item.split(",")
            alts.append(float(subitems[0]))
            depths.append(float(subitems[1]))
        alts = numpy.array(alts)
        depths = numpy.array(depths)
        refs = depths-alts

        passed_sites = (depths>0)*1.0
        if gene_name not in passed_sites_map:
            passed_sites_map[gene_name] = {v: {'location': (chromosome,location), 'sites': numpy.zeros((len(samples), len(samples)))} for v in allowed_variant_types}
            
            allele_counts_map[gene_name] = {v: {'locations':[], 'alleles':[]} for v in allowed_variant_types}
        
        
        passed_sites_map[gene_name][variant_type]['sites'] += passed_sites[:,None]*passed_sites[None,:]
        
        # zero out non-passed sites
        # (shouldn't be needed anymore)    
        refs = refs*passed_sites
        alts = alts*passed_sites
        depths = depths*passed_sites
        
        # calculate whether SNP has passed
        
        # Criteria used in Schloissnig et al (Nature, 2013)
        #total_alts = alts.sum()
        #total_depths = depths.sum()
        #pooled_freq = total_alts/((total_depths+(total_depths==0))
        #snp_passed = (freq>0.01) and (total_alts>=4) and ((total_depths-total_alts)>=4)
        
        # new version
        #alt_threshold = numpy.ceil(depths*0.05)+0.5 #at least one read above 5%.
        #alts = alts*((alts>alt_threshold))
        #snp_passed = (alts.sum()>0) and (pvalue<0.05)
        
        # "pop gen" version
        alt_lower_threshold = numpy.ceil(depths*0.05)+0.5 #at least one read above 5%.
        alts = alts*((alts>alt_lower_threshold))
        
        alt_upper_threshold = alt_lower_threshold
        snp_passed = ((alts>alt_upper_threshold).sum()>0) and (pvalue<0.05)
        
        # consensus approximation
        #alt_upper_threshold = depths*0.95
        #snp_passed = ((alts>alt_upper_threshold).sum()>0)
        
        
        #print alts.sum()>0, pvalue, (pvalue < 5e-02), snp_passed
        
        allele_counts = numpy.transpose(numpy.array([alts,refs]))
        
        allele_counts_map[gene_name][variant_type]['locations'].append((chromosome, location))
        allele_counts_map[gene_name][variant_type]['alleles'].append(allele_counts)
        
        num_sites_processed+=1
        if num_sites_processed%10000==0:
            sys.stderr.write("%dk sites processed...\n" % (num_sites_processed/1000))   
            if debug:
                break
    
    snp_file.close()

    for gene_name in passed_sites_map.keys():
        for variant_type in passed_sites_map[gene_name].keys():
            
            allele_counts_map[gene_name][variant_type]['alleles'] = numpy.array(allele_counts_map[gene_name][variant_type]['alleles'])

    return samples, allele_counts_map, passed_sites_map

###############################################################################
#
# Loads list of SNPs and counts of target sites from annotated SNPs file
#
# returns (lots of things, see below)
#
###############################################################################
def parse_gene_presences(species_name):
    
    # Open post-processed MIDAS output
    gene_presabs_file =  bz2.BZ2File("%sgenes/%s/genes_presabs.txt.bz2" % (data_directory, species_name),"r")
    
    line = gene_presabs_file.readline() # header
    items = line.split()
    samples = items[1:]
    
    
    gene_presence_matrix = []
    gene_names = []
    
    num_genes_processed = 0
    for line in gene_presabs_file:
        
        items = line.split()
        # Load information about gene
        gene_name = items[0]
        gene_presences = numpy.array([float(item) for item in items[1:]])
        
        if gene_presences.sum() > 0.5:
            # gene is present in at least one individual! 
            gene_presence_matrix.append(gene_presences)
            gene_names.append(gene_name)
        
        num_genes_processed+=1
        
    
    gene_presabs_file.close()
    gene_presence_matrix = numpy.array(gene_presence_matrix)

    return samples, gene_names, gene_presence_matrix

################################################################################
#
# Loads metaphlan2 genes
# returns a list of metaphlan2 genes
#
################################################################################
def load_metaphlan2_genes(desired_species_name):
    gene_file = open("%smetaphlan2_genes/%s_metaphlan2_genes_mapped.txt" % (data_directory, desired_species_name), 'r')
    
    metaphlan2_genes=[]
    for line in gene_file:
        metaphlan2_genes.append(line.strip())

    gene_file.close()    
    
    return metaphlan2_genes

########################################################################################
#
# Loads time data for HMP samples 
# Returns map from subject_id -> visno -> [[sample_id, study_day_1], [sample_id, study_day_2], etc]
#
#######################################################################################
def parse_subject_sample_time_map(filename=os.path.expanduser("~/ben_nandita_hmp_data/HMP_ids_time.txt")): 
    file = open(filename,"r")
    file.readline() # header
    
    
    subject_sample_time_map = {}
    
    for line in file:
        items = line.split("\t")
        subject_id= items[0].strip()
        sample_id = items[1].strip()
        visno     = int(items[5].strip())
        study_day = int(items[6].strip())

        if subject_id not in subject_sample_time_map:
            subject_sample_time_map[subject_id] = {}
                        
        subject_sample_time_map[subject_id][visno]=[sample_id,study_day]
        
    return subject_sample_time_map 


########################################################################################
#
# Returns index pairs for time points corresponding to the same subject_id.
# Also returns the corresponding visnos and days. 
#
#######################################################################################

def calculate_time_pairs(subject_sample_time_map, samples):
    index1=[]
    index2=[]
    visno=[]
    day=[]

    for subject_id in subject_sample_time_map.keys():
        visnos=subject_sample_time_map[subject_id].keys() #visit numbers
        if (len(visnos) > 1) and (1 in visnos):           
            if (subject_sample_time_map[subject_id][1][0] in samples): #check if first visit in samples 
                #iterate through visit numbers. Append the index, day, and visnos to their lists
                for i in visnos:        
                    if (subject_sample_time_map[subject_id][i][0] in samples) and (i !=1):
                        index1.append(samples.index(subject_sample_time_map[subject_id][1][0]))
                        index2.append(samples.index(subject_sample_time_map[subject_id][i][0]))
                        visno.append(i)
                        day.append(subject_sample_time_map[subject_id][i][1])
        
    time_pair_idxs = (numpy.array(index1,dtype=numpy.int32), numpy.array(index2,dtype=numpy.int32))

    return time_pair_idxs, visno, day


#######################    

if __name__=='__main__':

    pass
    
