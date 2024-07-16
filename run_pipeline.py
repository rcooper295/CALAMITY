from astropy.io import fits
from jwst.pipeline import Detector1Pipeline, Image2Pipeline
import argparse
import os

from jwst.ami import AmiAnalyzeStep, AmiNormalizeStep

# script for doing basic pipeline processing of AMI data
# options to run just one stage, or two, or all with CLI
# if running aminormalize, automatically generate calibration pairs OR
# accept input filename pairs in YAML file? (TBD)
# could also theoretically make/use an association file and run whole ami3 stage
# but then the amimulti and amilg products wouldn't be saved.



def run_detector1(files, outdir):
	if not os.path.exists(outdir):
		os.makedirs(outdir)
	for fn in files:
	    result1 = Detector1Pipeline()
	    result1.ipc.skip = True
	    result1.persistence.skip = True
	    result1.save_results = True
	    result1.save_calibrated_ramp = True
	    result1.output_dir = outdir
	    result1.run(fn)

def run_image2(files, outdir):
	if not os.path.exists(outdir):
		os.makedirs(outdir)
	for fn in files:
	    result2 = Image2Pipeline()
	    result2.photom.skip = True
	    result2.resample.skip = True
	    result2.save_results = True
	    result2.output_dir = outdir
	    result2.run(rateints)

def run_ami3(files, outdir, calib_pairs=None):
	if not os.path.exists(outdir):
		os.makedirs(outdir)
	for fn in files:
	    analyze = AmiAnalyzeStep()
	    analyze.save_results = True
	    analyze.firstfew = None
	    analyze.usebp = False 
	    analyze.oversample = 5
	    analyze.run_bpfix = True
	    analyze.output_dir = outdir
	    output_model, outputmodelmulti, lgmodel = analyze.run(calints)

	# define calibration pairs
	if calib_pairs is None:
		calib_pairs = make_pairs(files)
	else:
		# load YAML file of calibration pairs
		continue # for now
	# run ami_normalize to calibrate
	for (targfn, calfn) in calib_pairs:
		targoi = os.path.join(indir,targfn.replace('calints.fits','ami-oi.fits'))
		caloi = os.path.join(indir,targfn.replace('calints.fits','ami-oi.fits'))
		normalize = AmiNormalizeStep()
		normalize.output_dir = outdir
		normalize.save_results = True
		normalize.run(targoi,caloi)

def make_pairs(files):
    # calibrator exposures should have "is_psf" True in header
    # matched by filter, dither position
    # make dictionary of relevant keywords 
    # needs further testing         
    filedict = {}
    keywords = ['FILTER','IS_PSF','PATT_NUM','NUMDTHPT']
    for fn in files:
        hdr = fits.getheader(fn)
        filedict[fn] = {}
        for keyw in keywords:
            filedict[fn][keyw] = hdr[keyw]
    calpairs = []
    for fn1 in files:
        if filedict[fn1]['IS_PSF'] is False:
            for fn2 in files:
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

def run_all(files, outdir, calib_pairs=None):
	if files[0].split("_")[-1] != 'uncal.fits':
		print('Input files should be uncal.fits files')
	run_detector1(files, outdir)
	# save all outputs to the same directory; becomes input for following stages
	rateints = [os.path.join(outdir, os.path.basename(fn).replace('uncal','rateints')) for fn in files]
	run_image2(ratints, outdir)
	calints = [os.path.join(outdir, os.path.basename(fn).replace('uncal','calints')) for fn in files]
	run_ami3(calints, outdir, calib_pairs=calib_pairs)


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
