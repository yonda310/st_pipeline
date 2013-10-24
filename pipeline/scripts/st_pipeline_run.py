#! /usr/bin/env python
# @Created by Jose Fernandez
""" This is a terminal based API to run the ST pipeline on a single node
"""

##TODO : Unify argument parsers from different runners
import sys
import argparse
from main.core.pipeline import *

def main(argv):
    
    pipeline = Pipeline()
    
    #create a parser
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs=2)
    parser.add_argument('--output-folder', default="merged.json", help='Name of the output folder')
    parser.add_argument('--ids', default="",help='the name of the file containing the barcodes and the coordinates')
    parser.add_argument('--ref-map', default="", help= "<path_to_bowtie2_indexes>] = reference genome name for the genome that you want to use to align the reads")
    parser.add_argument('--ref-annotation', default="",help="select the reference(htseq requires a GTF file annotation file that you want to use to annotate")
    parser.add_argument('--expName', default="", help="the name of the experiment (outfile name)")
    parser.add_argument('--allowed-missed', default=6, help="number of allowed mismatches when mapping against the barcodes")
    parser.add_argument('--allowed-kimer', default=7, help="kMer length when mapping against the barcodes")
    parser.add_argument('--min-length-qual-trimming', default=28, help="minimum lenght of the sequence for mapping after trimming, shorter reads will be discarded")
    parser.add_argument('--mapping-fw-trimming', default=42, help="he number of bases to trim in the forward reads for the Mapping [24 + ID_LENGTH]")
    parser.add_argument('--mapping-rv-trimming', default=5, help="he number of bases to trim in the reverse reads for the Mapping")
    parser.add_argument('--length-id', default=18, help="length of ID, a.k.a. the length of the barcodes")
    parser.add_argument('--contaminant-bowtie2-index', default="", help="<path_to_bowtie2_indexes>] => When provided, reads will be filtered against the specified bowtie2 index, non-mapping reads will be saved and demultiplexed")
    parser.add_argument('--qual-64', action="store_true", default=False, help="use phred-64 quality instead of phred-33(default)")
    parser.add_argument('--htseq-mode', default="intersection-nonempty", help="Mode of Annotation when using HTSeq. Modes = {union,intersection-nonempty(default),intersection-strict}")
    parser.add_argument('--htseq-no-ambiguous', action="store_true", help="When using htseq discard reads annotating ambiguous genes")
    parser.add_argument('--start-id', default=0, help="start position of BARCODE ID [0]")
    parser.add_argument('--error-id', default=0, help="Id positional error [0]")
    parser.add_argument('--no-clean-up', action="store_true", default=False, help="do not remove temporary files at the end (useful for debugging)")
    parser.add_argument('--verbose', action="store_true", default=False, help="show extra information on the log")
    parser.add_argument('--bowtie-threads', default=8, help="Number of threads to run the mapper")
    parser.add_argument('--min-quality-trimming', default=20, help="minimum quality for trimming")
    parser.add_argument('--discard-fw', action="store_true", default=False, help="discard fw reads that maps uniquely")
    parser.add_argument('--discard-rv', action="store_true", default=False, help="discard rw reads that maps uniquely")
    parser.add_argument('--bowtie2-discordant', action="store_true", default=False, help="discard non-discordant alignments when mapping")
    parser.add_argument('--bin-path', default="", help="path to folder where binary executables are present")
    parser.add_argument('--log-file', default="", help="name of the file that we want to use to store the logs (default output to screen)")
    #parse arguments
    options = parser.parse_args()
    #init pipeline arguments
    pipeline.allowed_missed = int(options.allowed_missed)
    pipeline.allowed_kimera = int(options.allowed_kimer)
    pipeline.min_length_trimming = int(options.min_length_qual_trimming)
    pipeline.trimming_fw_bowtie = int(options.mapping_fw_trimming)
    pipeline.trimming_rw_bowtie = int(options.mapping_rv_trimming)
    pipeline.min_quality_trimming = int(options.min_quality_trimming) 
    pipeline.clean = options.no_clean_up
    pipeline.s = int(options.start_id)
    pipeline.l = int(options.length_id)
    pipeline.e = int(options.error_id)
    pipeline.threads = int(options.bowtie_threads)
    pipeline.verbose = options.verbose
    pipeline.ids = os.path.abspath(options.ids)
    pipeline.ref_map = os.path.abspath(options.ref_map)
    pipeline.ref_annotation = os.path.abspath(options.ref_annotation)
    pipeline.expName = options.expName
    pipeline.htseq_mode = options.htseq_mode
    pipeline.htseq_no_ambiguous = options.htseq_no_ambiguous
    pipeline.qual64 = options.qual_64
    pipeline.discard_fw = options.discard_fw
    pipeline.discard_rv = options.discard_rv
    pipeline.discordant = options.bowtie2_discordant
    pipeline.contaminant_bt2_index = options.contaminant_bowtie2_index
    pipeline.path = options.bin_path
    if(options.log_file != ""):
        pipeline.logfile = os.path.abspath(options.log_file)                
    pipeline.Fastq_fw = options.input[0]
    pipeline.Fastq_rv = options.input[1]
    #Hossein
    pipeline.output_folder=options.output_folder
        
    #should capture exceptions and deal with them here
    pipeline.load_parameters()
    pipeline.sanityCheck()
    pipeline.run()
        
if __name__ == "__main__":
    main(sys.argv[1:])
    

