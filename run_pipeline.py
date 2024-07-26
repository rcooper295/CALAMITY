from astropy.io import fits
from jwst.pipeline import Detector1Pipeline, Image2Pipeline
import argparse
import os
import time

from jwst.ami import AmiAnalyzeStep, AmiNormalizeStep

# script for doing basic pipeline processing of AMI data
# options to run just one stage, or two, or all with CLI
# if running aminormalize, automatically generate calibration pairs OR
# accept input filename pairs in YAML file? (TBD)
# could also theoretically make/use an association file and run whole ami3 stage
# but then the amimulti and amilg products wouldn't be saved.


def run_detector1(files, outdir, skipdark=True):
	toc = time.time()
	if not os.path.exists(outdir):
		os.makedirs(outdir)
	if files[0].split("_")[-1] != 'uncal.fits':
		# replace whatever the suffix is with uncal
		files = replace_suffix(files, 'uncal.fits')
	for fn in files:
		outpred = os.path.join(outdir, os.path.basename(fn).replace('uncal','rateints'))
		if os.path.exists(outpred):
			print('File already exists, not re-running')
			continue
		result1 = Detector1Pipeline()
		result1.ipc.skip = True
		if skipdark:
			result1.dark.skip = True
		result1.persistence.skip = True
		result1.save_results = True
		result1.save_calibrated_ramp = True
		result1.output_dir = outdir
		result1.run(fn)
	tic = time.time()
	print("Detector1 runtime: %.3f s" % (tic - toc))

def run_image2(files, outdir):
	toc = time.time()
	if not os.path.exists(outdir):
		os.makedirs(outdir)
	if files[0].split("_")[-1] != 'rateints.fits':
		# replace whatever the suffix is with rateints
		files = replace_suffix(files, 'rateints.fits', newdir=outdir)
	for fn in files:
		
		result2 = Image2Pipeline()
		result2.photom.skip = True
		result2.resample.skip = True
		result2.save_results = True
		result2.output_dir = outdir
		result2.run(fn)
	tic = time.time()
	print("Image2 runtime: %.3f s" % (tic - toc))

def run_ami3(files, outdir, calib_pairs=None):
	toc = time.time()
	if not os.path.exists(outdir):
		os.makedirs(outdir)
	if files[0].split("_")[-1] != 'calints.fits':
		# replace whatever the suffix is with calints
		files = replace_suffix(files, 'calints.fits', newdir=outdir)
	for fn in files:
		# skip TA files
		hdr = fits.getheader(fn)
		if hdr['EXP_TYPE'] != 'NIS_AMI':
			continue
		analyze = AmiAnalyzeStep()
		analyze.save_results = True
		analyze.firstfew = None
		analyze.usebp = False 
		analyze.oversample = 5
		analyze.run_bpfix = True
		analyze.output_dir = outdir
		output_model, outputmodelmulti, lgmodel = analyze.run(fn)

	# define calibration pairs
	if calib_pairs is None:
		calib_pairs = make_pairs(files)
	else:
		# load YAML file of calibration pairs
		pass # for now
	# run ami_normalize to calibrate
	for (targfn, calfn) in calib_pairs:
		targoi = os.path.join(indir,targfn.replace('calints.fits','ami-oi.fits'))
		caloi = os.path.join(indir,targfn.replace('calints.fits','ami-oi.fits'))
		normalize = AmiNormalizeStep()
		normalize.output_dir = outdir
		normalize.save_results = True
		normalize.run(targoi,caloi)
	tic = time.time()
	print("Ami3 runtime: %.3f s" % (tic - toc))
def make_pairs(files):
	# calibrator exposures should have "is_psf" True in header
	# matched by filter, dither position
	# make dictionary of relevant keywords 
	# needs further testing         
	filedict = {}
	keywords = ['FILTER','IS_PSF','PATT_NUM','NUMDTHPT']
	for fn in files:
		hdr = fits.getheader(fn)
		if hdr['EXP_TYPE'] != 'NIS_AMI':
			continue
		filedict[fn] = {}
		for keyw in keywords:
			filedict[fn][keyw] = hdr[keyw]
	calpairs = []
	for fn1 in files:
		if filedict[fn1]['IS_PSF'] is False:
			for fn2 in files:
				if hdr['EXP_TYPE'] != 'NIS_AMI':
					continue
				if ((filedict[fn2]['IS_PSF'] is True) &
					(filedict[fn2]['FILTER'] == filedict[fn1]['FILTER']) & 
					(filedict[fn2]['PATT_NUM'] == filedict[fn1]['PATT_NUM']) & 
					(filedict[fn2]['NUMDTHPT'] == filedict[fn1]['NUMDTHPT'])):
					calpairs.append((fn1,fn2))
				else:
					continue
		else:
			continue

	for (targ, cal) in calpairs:
		print("targ:", os.path.basename(targ),"cal:", os.path.basename(cal))

	return calpairs

def replace_suffix(files, newsuffix, newdir=None):
	newfiles = []
	for fn in files:
		splitlist = fn.split("_")
		splitlist[-1] = newsuffix
		newfn = "_".join(splitlist)
		if newdir:
			newfn = os.path.join(newdir,os.path.basename(newfn))
		newfiles.append(newfn)
	return newfiles

def run_all(files, outdir, calib_pairs=None):
	bigtoc = time.time()
	run_detector1(files, outdir)
	# save all outputs to the same directory; becomes input for following stages
	#rateints = [os.path.join(outdir, os.path.basename(fn).replace('uncal','rateints')) for fn in files]
	run_image2(files, outdir)
	#calints = [os.path.join(outdir, os.path.basename(fn).replace('uncal','calints')) for fn in files]
	run_ami3(files, outdir, calib_pairs=calib_pairs)
	bigtic = time.time()
	print("Full runtime: %.3f s" % (bigtic - bigtoc))

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("files", nargs='+', help="List of files to process")
	parser.add_argument("outdir", help="Directory to save output files")
	parser.add_argument("--calib_pairs", default=None, help="YAML file of calibration pairs, not yet implemented")
	parser.add_argument("--stages", nargs='+',action='store', type=str, help="Which pipeline stages to run (1 2 3). Default is to run all.")
	args = parser.parse_args()

	if args.stages:
		if "1" in args.stages:
			print('Going to run detector1')
			run_detector1(args.files, args.outdir)

		if "2" in args.stages:
			print('Going to run image2')
			run_image2(args.files, args.outdir)

		if "3" in args.stages:
			print('Going to run ami3')
			run_ami3(args.files, args.outdir, calib_pairs=args.calib_pairs)

	else:
		print('Going to run all stages')
		run_all(args.files, args.outdir, calib_pairs=args.calib_pairs)
