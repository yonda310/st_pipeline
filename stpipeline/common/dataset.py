""" 
This module contains routines to create
a ST dataset and some statistics. The dataset
will contain several files with the ST data in different
formats
"""
import sys
import pysam
import os
import numpy as np
from collections import defaultdict
import pandas as pd
from stpipeline.common.clustering import *
from stpipeline.common.sam_utils import parseUniqueEvents
from stpipeline.common.sam_utils import parseUniqueEvents_byCoordinate
import logging

def createDataset(input_file,
                  qa_stats,
                  gff_filename,
                  umi_cluster_algorithm="hierarchical",
                  umi_allowed_mismatches=1,
                  umi_counting_offset=250,
                  output_folder=None,
                  output_template=None,
                  verbose=True):
    """
    The functions parses the reads in BAM format
    that have been annotated and demultiplexed (containing spatial barcode).
    It then groups them by gene-barcode to count reads accounting for duplicates
    using the UMIs (clustering them suing the strand and start position). 
    It outputs the records in a matrix of counts in TSV format and BED format and it also 
    writes out some statistics.
    :param input_file: the file with the annotated-demultiplexed records in BAM format
    :param qa_stats: the Stats object to add some stats (THIS IS PASSED BY REFERENCE)
    :param umi_cluster_algorithm: the clustering algorithm to cluster UMIs
    :param umi_allowed_mismatches: the number of miss matches allowed to remove
                                  duplicates by UMIs
    :param umi_counting_offset: the number of bases allowed as offset (start position) when counting UMIs
    :param output_folder: path to place the output files
    :param output_template: the name of the dataset
    :param verbose: True if we can to collect the stats in the logger
    :type input_file: str
    :type umi_cluster_algorithm: str
    :type umi_allowed_mismatches: boolean
    :type umi_counting_offset: integer
    :type output_folder: str
    :type output_template: str
    :type verbose: bool
    :raises: RuntimeError,ValueError,OSError,CalledProcessError
    """
    logger = logging.getLogger("STPipeline")
    
    if not os.path.isfile(input_file):
        error = "Error creating dataset, input file not present {}\n".format(input_file)
        logger.error(error)
        raise RuntimeError(error)
      
    if output_template:
        filenameDataFrame = "{}_stdata.tsv".format(output_template)
        filenameReadsBED = "{}_reads.bed".format(output_template)
    else:
        filenameDataFrame = "stdata.tsv"
        filenameReadsBED = "reads.bed"
         
    # Some counters
    total_record = 0
    discarded_reads = 0
    
    # Obtain the clustering function
    if umi_cluster_algorithm == "naive":
        group_umi_func = countUMINaive
    elif umi_cluster_algorithm == "hierarchical":
        group_umi_func = countUMIHierarchical
    elif umi_cluster_algorithm == "Adjacent":
        group_umi_func = dedup_adj
    elif umi_cluster_algorithm == "AdjacentBi":
        group_umi_func = dedup_dir_adj
    else:
        error = "Error creating dataset.\n" \
        "Incorrect clustering algorithm {}".format(umi_cluster_algorithm)
        logger.error(error)
        raise RuntimeError(error)
 
    # Containers needed to create the data frame
    list_row_values = list()
    list_indexes = list()   
    
    import sys
    # Parse unique events to generate the unique counts and the BED file    
    all_unique_events = parseUniqueEvents_byCoordinate(input_file, gff_filename)
    with open(os.path.join(output_folder, filenameReadsBED), "w") as reads_handler:
        # Unique events is a dict() [spot][gene] -> list(transcripts)
        for gene, spots in all_unique_events:
            transcript_counts_by_spot = {}
            for spot_coordinates, reads in spots.iteritems():
                #sys.stderr.write('INFO:: processing gene '+gene+' spot '+str(spot_coordinates)+'\n')
                (x,y) = spot_coordinates
                # Re-compute the read count accounting for duplicates using the UMIs
                # Transcripts is the list of transcripts (chrom, start, end, clear_name, mapping_quality, strand, UMI)
                # First
                # Get the original number of transcripts (reads)
                read_count = len(reads)
                # Sort transcripts by strand and start position
                sorted_reads = sorted(reads, key = lambda x: (x[5], x[1]))
                # Group transcripts by strand and start-position allowing an offset
                # And then performs the UMI clustering in each group to finally
                # compute the gene count as the sum of the unique UMIs for each group (strand,start,offset)
                grouped_reads = defaultdict(list)
                unique_transcripts = list()
                # TODO A probably better approach is to get the mean of all the start positions
                # and then makes mean +- 300bp (user defined) a group to account for the library
                # size variability and then group the rest of transcripts normally by (strand, start, position).
                for i in xrange(read_count-1):
                    current = sorted_reads[i]
                    nextone = sorted_reads[i+1]
                    (current_chrom, current_start, current_end, current_clear_name, current_mapping_quality,current_strand, current_UMI) = current
                    (nextone_chrom, nextone_start, nextone_end, nextone_clear_name, nextone_mapping_quality, nextone_strand, nextone_UMI) = nextone
                    grouped_reads[current_UMI].append(current)
                    if abs(current_start - nextone_start) > umi_counting_offset or current_strand != nextone_strand:
                        # A new group has been reached (strand, start-pos, offset)
                        # Compute unique UMIs by hamming distance
                        unique_umis = group_umi_func(grouped_reads.keys(),umi_allowed_mismatches)
                        # Choose 1 random transcript for the clustered transcripts (by UMI)
                        unique_transcripts += [random.choice(grouped_reads[u_umi]) for u_umi in unique_umis]
                        # Reset the container
                        grouped_reads = defaultdict(list)
                # We process the last one and more transcripts if they were not processed
                lastone = sorted_reads[read_count-1]
                grouped_reads[lastone[6]].append(lastone)
                unique_umis = group_umi_func(grouped_reads.keys(),umi_allowed_mismatches)
                unique_transcripts += [random.choice(grouped_reads[u_umi]) for u_umi in unique_umis]
                # The new gene count                           
                transcript_count = len(unique_transcripts)
                assert transcript_count > 0 and transcript_count <= read_count   
                # Update the discarded transcripts count
                discarded_reads += (read_count - transcript_count)
                # Update read counts in the container (replace the list
                # of transcripts for a number so it can be exported as a data frame)
                transcript_counts_by_spot["{0}x{1}".format(x, y)] = transcript_count
                # Write every unique transcript to the BED output (adding spot coordinate and gene name)
                for read in unique_transcripts:
                    reads_handler.write("{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\t{7}\t{8}\n".format(read[0],
                                                                                               read[1],
                                                                                               read[2],
                                                                                               read[3],
                                                                                               read[4],
                                                                                               read[5],
                                                                                               gene,
                                                                                               x,y)) 
                # keep a counter of the number of unique events (spot - gene) processed
                total_record += 1
                #sys.stderr.write('INFO:: completed gene '+gene+' spot '+str(spot_coordinates)+'\n')
                
            # Add spot and dict [gene] -> count to containers
            list_indexes.append(gene)
            list_row_values.append(transcript_counts_by_spot)
            #sys.stderr.write('INFO:: completed all spots in gene '+gene+'\n')
            
    if total_record == 0:
        error = "Error creating dataset, input file did not contain any transcript\n"
        logger.error(error)
        raise RuntimeError(error)
    
    # Create the data frame
    counts_table = pd.DataFrame(list_row_values, index=list_indexes)
    counts_table.fillna(0, inplace=True)
    counts_table=counts_table.T
    
    # Compute some statistics
    total_barcodes = len(counts_table.index)
    total_transcripts = np.sum(counts_table.values, dtype=np.int32)
    number_genes = len(counts_table.columns)
    max_count = counts_table.values.max()
    min_count = counts_table.values.min()
    aggregated_spot_counts = counts_table.sum(axis=1).values
    aggregated_gene_counts = (counts_table != 0).sum(axis=1).values
    max_genes_feature = aggregated_gene_counts.max()
    min_genes_feature = aggregated_gene_counts.min()
    max_reads_feature = aggregated_spot_counts.max()
    min_reads_feature = aggregated_spot_counts.min()
    average_reads_feature = np.mean(aggregated_spot_counts)
    average_genes_feature = np.mean(aggregated_gene_counts)
    std_reads_feature = np.std(aggregated_spot_counts)
    std_genes_feature = np.std(aggregated_gene_counts)
        
    # Print some statistics
    if verbose:
        logger.info("Number of unique molecules present: {}".format(total_transcripts))
        logger.info("Number of unique events (gene-feature) present: {}".format(total_record))
        logger.info("Number of unique genes present: {}".format(number_genes))
        logger.info("Max number of genes over all features: {}".format(max_genes_feature))
        logger.info("Min number of genes over all features: {}".format(min_genes_feature))
        logger.info("Max number of unique molecules over all features: {}".format(max_reads_feature))
        logger.info("Min number of unique molecules over all features: {}".format(min_reads_feature))
        logger.info("Average number genes per feature: {}".format(average_genes_feature))
        logger.info("Average number unique molecules per feature: {}".format(average_reads_feature))
        logger.info("Std number genes per feature: {}".format(std_genes_feature))
        logger.info("Std number unique molecules per feature: {}".format(std_reads_feature))
        logger.info("Max number of unique molecules over all unique events: {}".format(max_count))
        logger.info("Min number of unique molecules over all unique events: {}".format(min_count))
        logger.info("Number of discarded reads (possible duplicates): {}".format(discarded_reads))
        
    # Update the QA object
    qa_stats.reads_after_duplicates_removal = int(total_transcripts)
    qa_stats.unique_events = total_record
    qa_stats.barcodes_found = total_barcodes
    qa_stats.genes_found = number_genes
    qa_stats.duplicates_found = discarded_reads
    qa_stats.max_genes_feature = max_genes_feature
    qa_stats.min_genes_feature = min_genes_feature
    qa_stats.max_reads_feature = max_reads_feature
    qa_stats.min_reads_feature = min_reads_feature
    qa_stats.max_reads_unique_event = max_count
    qa_stats.min_reads_unique_event = min_count
    qa_stats.avergage_gene_feature = average_genes_feature
    qa_stats.average_reads_feature = average_reads_feature
     
    # Write data frame to file
    counts_table.to_csv(os.path.join(output_folder, filenameDataFrame), sep="\t", na_rep=0)       
