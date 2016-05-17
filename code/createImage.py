import astropy.wcs
import astropy.units as u
import astropy.coordinates as astroCoords
import numpy as np
import matplotlib.mlab as mlab
import astropy.convolution as conv
import matplotlib.pyplot as plt
from astropy.io import fits
from scipy.spatial.distance import euclidean

class createImage(object):

    def createSimpleBackground(self, xPixels, yPixels, backgroundLevel):
        "Creates 2-d array with given number of pixels."
        backgroundArray = np.ones((xPixels, yPixels))*backgroundLevel
        return backgroundArray

    def createStarSet(self, numImages, imSize, meanFlux, invDensity, psfSigma):
        starArray = np.zeros((imSize))
        numStars = int(imSize[0]*imSize[1]/invDensity)
        xCenters = np.random.randint(0, imSize[0], size=numStars)
        yCenters = np.random.randint(0, imSize[1], size=numStars)
        fluxArray = np.array(np.ones(numStars)*meanFlux +
                                  np.random.uniform(-0.5*meanFlux, 0.5*meanFlux, size=numStars))
        for star in range(0, numStars):
            starArray += self.createGaussianSource([xCenters[star], yCenters[star]], psfSigma,
                                                    imSize, fluxArray[star])

        starImagesArray = np.zeros((numImages, imSize[0], imSize[1]))
        for imNum in range(0, numImages):
            starImagesArray[imNum] = np.copy(starArray)

        return starImagesArray, np.transpose([xCenters, yCenters]), fluxArray

    def applyNoise(self, imageArray):
        noise_added = np.random.poisson(imageArray)
        return noise_added

    def convolveGaussian(self, image, gaussSigma, **kwargs):

        if (type(gaussSigma) is int) or (type(gaussSigma) is float):
            gaussSigma = np.array([gaussSigma, gaussSigma])

        gRow = conv.Gaussian1DKernel(gaussSigma[0])
        gCol = conv.Gaussian1DKernel(gaussSigma[1])
        convImage = np.copy(image)

        for rowNum in range(0, len(image)):
            convImage[rowNum] = conv.convolve(convImage[rowNum], gRow, **kwargs)
        for col in range(0, len(image.T)):
            convImage[:,col] = conv.convolve(convImage[:,col], gCol, **kwargs)

        return convImage

    def convolveSquaredGaussian(self, image, gaussSigma):

        if (type(gaussSigma) is int) or (type(gaussSigma) is float):
            gaussSigma = np.array([gaussSigma, gaussSigma])

        gRow = conv.Gaussian1DKernel(gaussSigma[0])
        gSqRow = conv.CustomKernel(np.power(gRow.array, 2))
        gCol = conv.Gaussian1DKernel(gaussSigma[1])
        gSqCol = conv.CustomKernel(np.power(gCol.array, 2))
        convImage = np.copy(image)

        for rowNum in range(0, len(image)):
            convImage[rowNum] = conv.convolve(convImage[rowNum], gSqRow, boundary=None)
        for col in range(0, len(image.T)):
            convImage[:,col] = conv.convolve(convImage[:,col], gSqCol, boundary=None)

        return convImage

    def createGaussianSource(self, centerArr, sigmaArr, imSize, fluxVal):
        """Creates 2-D Gaussian Point Source

        centerArr: [xCenter, yCenter] in pixels
        sigmaArr: [xSigma, ySigma] in pixels
        imSize: [xPixels, yPixels]
        fluxVal: Flux value of point source"""

        sourceIm = np.zeros((imSize))
        sourceIm[centerArr[0], centerArr[1]] = fluxVal
        newSource = self.convolveGaussian(sourceIm, sigmaArr)

        return newSource

    def calcCenters(self, startLocArr, velArr, timeArr):

        startLocArr = np.array(startLocArr)
        velArr = np.array(velArr)
        centerArr = []
        for time in timeArr:
            centerArr.append(startLocArr + (velArr*time))
        return np.array(centerArr)

    def sumImage(self, imagePieces):

        shape = np.shape(imagePieces[0])
        totalImage = np.zeros((shape))
        for imagePart in imagePieces:
            totalImage += imagePart
        return totalImage

    def createSingleSet(self, outputName, startLocArr, velArr, timeArr, imSize,
                        bkgrdLevel, sourceLevel, sigmaArr, sourceNoise = True, bkgrdNoise = True,
                        addStars = True, starNoise = True, meanIntensity = None, invDensity = 30**2):

        "Create a set of images with a single gaussian psf moving over time."

        objCenters = self.calcCenters(startLocArr, velArr, timeArr)
        imageArray = np.zeros((len(timeArr), imSize[0], imSize[1]))
        varianceArray = np.zeros((len(timeArr), imSize[0], imSize[1]))
        for imNum in xrange(0, len(timeArr)):
            background = self.createSimpleBackground(imSize[0], imSize[1], bkgrdLevel)
            if bkgrdNoise == True:
                noisy_background = self.applyNoise(background)
            else:
                noisy_background = background

            if sourceNoise == True:
                source = self.createGaussianSource(objCenters[imNum], sigmaArr, imSize, np.random.poisson(sourceLevel))
            else:
                source = self.createGaussianSource(objCenters[imNum], sigmaArr, imSize, sourceLevel)

            imageArray[imNum] = self.sumImage([source, noisy_background])
            varianceArray[imNum] = noisy_background - background

        if addStars == True:
            if meanIntensity == None:
                meanIntensity = 40.*bkgrdLevel
            stars, starLocs, starFlux = self.createStarSet(len(timeArr), imSize, meanIntensity, invDensity, sigmaArr)
            if starNoise == True:
                noisy_stars = self.applyNoise(stars)
            else:
                noisy_stars = stars
            imageArray += noisy_stars
            np.savetxt(str(outputName + '_stars.dat'), starLocs)
            np.savetxt(str(outputName + '_starsFlux.dat'), starFlux)

        hdu = fits.PrimaryHDU(imageArray)
        hdu2 = fits.PrimaryHDU(varianceArray)
        hdu.writeto(str(outputName + '.fits'))
        hdu2.writeto(str(outputName + '_var.fits'))

class analyzeImage(object):

    def calcArrayLimits(self, imShape, centerX, centerY, scaleFactor, sigmaArr):

        xmin = int(centerX-(scaleFactor*sigmaArr[0]))
        xmax = int(1+centerX+(scaleFactor*sigmaArr[0]))
        ymin = int(centerY-(scaleFactor*sigmaArr[1]))
        ymax = int(1+centerY+(scaleFactor*sigmaArr[1]))
        if ((xmin < 0) | (ymin < 0) | (xmax >= imShape[0]) | (ymax >= imShape[1])):
            maxXOff = xmax-imShape[0]+1
            maxYOff = ymax-imShape[1]+1
            minXOff = xmin*(-1.)
            minYOff = ymin*(-1.)
            offset = np.max([maxXOff, maxYOff, minXOff, minYOff])
            xmin += offset
            xmax -= offset
            ymin += offset
            ymax -= offset
        else:
            offset = None

        return xmin, xmax, ymin, ymax, offset

    def createAperture(self, imShape, locationArray, sigma, scaleFactor, mask=False):

        apertureArray = np.zeros((imShape))

        if len(np.shape(sigma)) < 1:
            radius=scaleFactor*sigma
        else:
            radius = scaleFactor*sigma[0]

        if len(np.shape(locationArray)) < 2:
            locationArray = [locationArray]

        for center in locationArray:
            centerX = center[0]
            centerY = center[1]
            for ix in range(0, int(imShape[0])):
                for iy in range(0, int(imShape[1])):
                    distX = centerX - ix
                    distY = centerY - iy
                    if np.sqrt((distX**2)+(distY**2)) <= radius:
                        apertureArray[ix, iy] = 1.

        if mask==True:
            apertureArray -= 1
            apertureArray = np.abs(apertureArray)

        return apertureArray

    def trackSingleObject(self, imageArray, gaussSigma):

        objectCoords = []
        for image in imageArray:
            newImage = createImage().convolveGaussian(image, gaussSigma)
            maxIdx = np.argmax(newImage)
            objectCoords.append(np.unravel_index(maxIdx, np.shape(newImage)))
        return objectCoords

    def plotSingleTrajectory(self, imageArray, gaussSigma):

        objCoords = self.trackSingleObject(imageArray, gaussSigma)
        fig = plt.figure(figsize=(12,12))
        plt.plot(np.array(objCoords)[:,0], np.array(objCoords)[:,1], '-ko')
        plt.xlim((0, np.shape(imageArray[0])[0]))
        plt.ylim((0, np.shape(imageArray[0])[1]))

        return fig

    def calcSNR(self, image, centerArr, gaussSigma, background, imSize, apertureScale=1.6):

        if isinstance(background, np.ndarray):
            backgroundArray = background
        else:
            backgroundArray = np.ones((imSize))*background

        apertureScale = 1.6 #See derivation here: http://wise2.ipac.caltech.edu/staff/fmasci/GaussApRadius.pdf
        aperture = self.createAperture(imSize, centerArr, apertureScale, gaussSigma[0])
        sourceCounts = np.sum(image*aperture)
        if sourceCounts < 0:
            sourceCounts = 0.0
        noiseCounts = np.sum(backgroundArray*aperture)

        snr = sourceCounts/np.sqrt(sourceCounts+noiseCounts)
        return snr

    def calcTheorySNR(self, sourceFlux, centerArr, gaussSigma, background, imSize, apertureScale=1.6):

        if isinstance(background, np.ndarray):
            backgroundArray = background
        else:
            backgroundArray = np.ones((imSize))*background

        sourceTemplate = createImage().createGaussianSource(centerArr, gaussSigma, imSize, sourceFlux)

        aperture = self.createAperture(imSize, centerArr, apertureScale, gaussSigma[0])
        sourceCounts = np.sum(sourceTemplate*aperture)
        noiseCounts = np.sum(backgroundArray*aperture)

        snr = sourceCounts/np.sqrt(sourceCounts+noiseCounts)
        return snr

    def createPostageStamp(self, imageArray, objectStartArr, velArr, timeArr, gaussSigma, scaleFactor,
                           starLocs = None):

        singleImagesArray = []
        stampWidth = np.array(np.array(gaussSigma)*scaleFactor, dtype=int)
        stampImage = np.zeros(((2*stampWidth)+1))
        if len(np.shape(imageArray)) < 3:
            imageArray = [imageArray]

        measureCoords = createImage().calcCenters(objectStartArr, velArr, timeArr)
        if len(np.shape(measureCoords)) < 2:
            measureCoords = [measureCoords]
        for centerCoords in measureCoords:
            if (centerCoords[0] + stampWidth[0] + 1) > np.shape(imageArray[0])[0]:
                raise ValueError('The boundaries of your postage stamp for one of the images go off the edge')
            elif (centerCoords[0] - stampWidth[0]) < 0:
                raise ValueError('The boundaries of your postage stamp for one of the images go off the edge')
            elif (centerCoords[1] + stampWidth[1] + 1) > np.shape(imageArray[0])[1]:
                raise ValueError('The boundaries of your postage stamp for one of the images go off the edge')
            elif (centerCoords[1] - stampWidth[1]) < 0:
                raise ValueError('The boundaries of your postage stamp for one of the images go off the edge')

        i=0
        for image in imageArray:
            xmin = np.rint(measureCoords[i,0]-stampWidth[0])
            xmax = xmin + stampWidth[0]*2 + 1
            ymin = np.rint(measureCoords[i,1]-stampWidth[1])
            ymax = ymin + stampWidth[1]*2 + 1
            if starLocs is None:
                stampImage += image[xmin:xmax, ymin:ymax]
                singleImagesArray.append(image[xmin:xmax, ymin:ymax])
            else:
                starInField = False
                for star in starLocs:
                    distX = star[0] - measureCoords[i,0]
                    distY = star[1] - measureCoords[i,1]
                    if np.sqrt((distX**2)+(distY**2)) <= scaleFactor*gaussSigma[0]:
                        print star
                        starInField = True
                if starInField == False:
                    stampImage += image[xmin:xmax, ymin:ymax]
                    singleImagesArray.append(image[xmin:xmax, ymin:ymax])
                else:
                    print 'Star in Field for Image ', str(i+1)

            i+=1
        return stampImage, singleImagesArray

    def addMask(self, imageArray, locations, gaussSigma):

        maskedArray = np.zeros((np.shape(imageArray)))
        scaleFactor = 4.
        i = 0
        for image in imageArray:
            maskedArray[i] = image * self.createAperture(np.shape(image), locations, scaleFactor, gaussSigma, mask=True)
            i+=1

        return maskedArray

    def definePossibleTrajectories(self, psfSigma, vmin, vmax, maxTime):
        maxRadius = vmax*maxTime
        maxSep = psfSigma*2
        minRadius = vmin*maxTime
        numSteps = int(np.ceil(maxRadius/maxSep))*2
        theta = maxSep/maxRadius
        vRowStart = maxRadius
        vColStart = 0.
        numTraj = int(np.ceil(np.pi*2./theta))
        vRow = np.zeros(numTraj)
        vCol = np.zeros(numTraj)
        vRow[0] = vRowStart
        vCol[0] = vColStart
        for traj in range(1,numTraj):
            vRow[traj] = vRow[traj-1]*np.cos(theta) - vCol[traj-1]*np.sin(theta)
            vCol[traj] = vRow[traj-1]*np.sin(theta) + vCol[traj-1]*np.cos(theta)
        totVRow = np.zeros(numTraj*numSteps)
        totVCol = np.zeros(numTraj*numSteps)
        for stepNum in range(0, numSteps):
            totVRow[numTraj*stepNum:numTraj*(stepNum+1)] = (vRow/numSteps)*(stepNum+1)
            totVCol[numTraj*stepNum:numTraj*(stepNum+1)] = (vCol/numSteps)*(stepNum+1)

        totVRow/=maxTime
        totVCol/=maxTime

        final_positions = np.zeros((len(totVRow), 2))
        for vel_num in xrange(len(totVRow)):
            final_positions[vel_num, 0] = totVRow[vel_num]*maxTime
            final_positions[vel_num, 1] = totVCol[vel_num]*maxTime
        print 'here', len(totVRow)
        keep_idx = [0]
        for pos_idx in xrange(0, len(final_positions)):
            if pos_idx % 100 == 0:
                print pos_idx
            keep_val = True
            for prev_idx in keep_idx:
                if keep_val is False:
                    break
                elif euclidean(final_positions[pos_idx], [0,0]) < maxSep:
                    keep_val=False
                elif euclidean(final_positions[pos_idx], [0,0]) < minRadius:
                    keep_val=False
                elif euclidean(final_positions[pos_idx], final_positions[prev_idx]) < maxSep:
                    keep_val=False
            if keep_val is True:
                keep_idx.append(pos_idx)
        if euclidean(final_positions[0], [0,0]) < maxSep:
            keep_idx.pop(0)
#        print keep_idx
#        print final_positions[keep_idx]

#        totVRow = np.append(totVRow, 0.)
#        totVCol = np.append(totVCol, 0.)
        print len(keep_idx)
        return totVRow[keep_idx], totVCol[keep_idx], numSteps

    def findLikelyTrajectories(self, psiArray, phiArray,
                               psfSigma, v_arr, maxTimeStep, timeArr,
                               xRange=None, yRange=None, numResults=10):

        vRow, vCol, numSteps = self.definePossibleTrajectories(psfSigma, v_arr[0], v_arr[1], maxTimeStep)
        velArr = np.array([vRow, vCol]).T

        psfPixelArea = np.pi*(psfSigma**2)
        tempResults = int(np.ceil(psfPixelArea)*numResults)*5

        topVel = np.zeros((tempResults, 2))
        topT0 = np.zeros((tempResults,2))
        topScores = np.zeros(tempResults)
        topAlpha = np.zeros(tempResults)
        if xRange is None:
            x_min = 0
            x_max = np.shape(psiArray[0])[0]
        else:
            x_min = xRange[0]
            x_max = xRange[1]
        if yRange is None:
            y_min = 0
            y_max = np.shape(psiArray[0])[1]
        else:
            y_min = yRange[0]
            y_max = yRange[1]
        for rowPos in xrange(x_min, x_max):
            print rowPos
            for colPos in xrange(y_min, y_max):
                objectStartArr = np.zeros((len(vRow),2))
                objectStartArr[:,0] += rowPos
                objectStartArr[:,1] += colPos
                alphaArray, nuArray = self.calcAlphaNu(psiArray, phiArray, objectStartArr, velArr, timeArr)
                for objNu, objAlpha, objVel in zip(nuArray, alphaArray, velArr):
                    if objNu > np.min(topScores):
                        idx = np.argmin(topScores)
                        topScores[idx] = objNu
                        topT0[idx] = [rowPos, colPos]
                        topVel[idx] = objVel
                        topAlpha[idx] = objAlpha

        rankings = np.argsort(topScores)[-1::-1]
        keepVel = np.ones((numResults, 2)) * (999.) # To tell if it has been changed or not
        keepT0 = np.zeros((numResults, 2))
        keepScores = np.zeros(numResults)
        keepAlpha = np.zeros(numResults)

        resultsSet = 0
        for objNum in range(0,tempResults):
            testT0 = topT0[rankings][objNum]
            testVel = topVel[rankings][objNum]
            keepVal = True
            for t0, vel in zip(keepT0, keepVel):
                if ((euclidean(testT0, t0) <= psfSigma) and ((euclidean(testT0+(testVel*timeArr[-1]),
                                                                       t0+(vel*timeArr[-1])) <= psfSigma))):
                    keepVal=False
            if keepVal == True:
                keepT0[resultsSet] = testT0
                keepVel[resultsSet] = testVel
                keepScores[resultsSet] = topScores[rankings][objNum]
                keepAlpha[resultsSet] = topAlpha[rankings][objNum]
                resultsSet += 1
            if resultsSet == numResults:
                break
        print "\nTop %i results" %numResults
        print "Starting Positions: \n", keepT0
        print "Velocity Vectors: \n", keepVel
        print "Likelihood: \n", keepScores
        print "Best estimated flux: \n", keepAlpha

        return keepT0, keepVel, keepScores, keepAlpha

    def calcPsi(self, imageArray, psfSigma, verbose=False, starLocs=None, background=None, mask=None):

        if len(np.shape(imageArray)) == 2:
            imageArray = [imageArray]

        if starLocs is not None:
            scaleFactor = 4.
            mask = self.createAperture(np.shape(imageArray[0]), starLocs,
                                       scaleFactor, psfSigma, mask=True)
        elif mask is None:
            mask = np.ones(np.shape(imageArray[0]))

        if isinstance(background, np.ndarray):
            backgroundArray = background
        else:
            backgroundArray = np.ones((np.shape(imageArray[0])))*background

        i=0
        likeImageArray = []
        for image, backgroundImage in zip(imageArray, backgroundArray):
            print str('On Image ' + str(i+1) + ' of ' + str(len(imageArray)))
            newImage = np.copy(image)

            if background is not None:
                likelihoodImage = createImage().convolveGaussian((1/backgroundImage)*((newImage*mask)), psfSigma)
            else:
                likelihoodImage = createImage().convolveGaussian(((newImage*mask)-(backgroundImage*mask)), psfSigma)
            #if starLocs is not None:
                #likelihoodImage = mask*likelihoodImage

            likeImageArray.append(likelihoodImage)
            i+=1

        return likeImageArray

    def calcPhi(self, varianceImArray, psfSigma, verbose=False, starLocs=None,
                mask=None):

        if len(np.shape(varianceImArray)) == 2:
            varianceImArray = [varianceImArray]

        if starLocs is not None:
            scaleFactor = 4.
            mask = self.createAperture(np.shape(varianceImArray[0]), starLocs,
                                       scaleFactor, psfSigma, mask=True)
        elif mask is None:
            mask = np.ones(np.shape(varianceImArray[0]))

        i=0
        likeImageArray = np.zeros(np.shape(varianceImArray))

        for varianceImage in varianceImArray:
            print str('On Image ' + str(i+1) + ' of ' + str(len(likeImageArray)))
            # for rowPos in range(0, np.shape(likeImageArray[i])[0]):
            #     print rowPos
            #     for colPos in range(0, np.shape(likeImageArray[i])[1]):
            #         psfImage = createImage().createGaussianSource([rowPos, colPos], [psfSigma, psfSigma], np.shape(likeImageArray[i]), 1.)
            #         if background != 0.:
            #             psfImage /= backgroundImage
            #         psfSquared = createImage().convolveGaussian(psfImage, [psfSigma, psfSigma])
            #         likeImageArray[i][rowPos, colPos] = psfSquared[rowPos, colPos]
            likeImageArray[i] = createImage().convolveSquaredGaussian((1/varianceImage)*mask, [psfSigma, psfSigma])

            if starLocs is not None:
                likeImageArray[i] = mask*likeImageArray[i]
            i+=1

        return likeImageArray

    def calcAlphaNu(self, psiArray, phiArray, objectStartArr, velArr, timeArr):

        if len(np.shape(psiArray)) == 2:
            psiArray = [psiArray]
            phiArray = [phiArray]

        measureCoords = []
        multObjects = False
        if len(np.shape(objectStartArr)) > 1:
            multObjects = True
            for objNum in range(0, len(objectStartArr)):
                measureCoords.append(createImage().calcCenters(objectStartArr[objNum], velArr[objNum], timeArr))
        else:
            measureCoords.append(createImage().calcCenters(objectStartArr, velArr, timeArr))
            measureCoords = np.array(measureCoords)
            objectStartArr = [objectStartArr]

        alphaMeasurements = []
        nuMeasurements = []
        for objNum in range(0, len(objectStartArr)):
            psiTotal = 0
            phiTotal = 0
            for imNum in range(0, len(psiArray)):
                try:
                    psiTotal += psiArray[imNum][measureCoords[objNum][imNum][0], measureCoords[objNum][imNum][1]]
                    phiTotal += phiArray[imNum][measureCoords[objNum][imNum][0], measureCoords[objNum][imNum][1]]
                except:
                    continue
            if (phiTotal != 0):
                alphaMeasurements.append(psiTotal/phiTotal)
                nuMeasurements.append(psiTotal/np.sqrt(phiTotal))
            else:
                alphaMeasurements.append(np.nan)
                nuMeasurements.append(np.nan)

        return alphaMeasurements, nuMeasurements

    def findLikelyTrajectoriesParallel(self, psiArray, phiArray, psfSigma,
                                       vMinMax, maxTimeStep, timeArr,
                                       numResults=10, xRange=None,
                                       yRange=None, processes=1):

        import pathos.multiprocessing as mp

        pool = mp.ProcessingPool(processes)

        psiList = [psiArray]*processes
        phiList = [phiArray]*processes
        psfSigmaList = [psfSigma]*processes
        vMaxList = [vmax]*processes
        maxTimeStepList = [maxTimeStep]*processes
        timeArrList = [timeArr]*processes
        numResultsList = [numResults]*processes
        xRangeList = []
        yRangeList = []

        max_overlap = vmax*timeArr[-1]
        x0 = 0
        y0 = 0
        if xRange is not None:
            x_min = xRange[0]
            max_x = xRange[1] - xRange[0]
        else:
            x_min = 0
            max_x = np.shape(psiArray[0])[0]
        if yRange is not None:
            y_min = yRange[0]
            max_y = yRange[1] - yRange[0]
        else:
            y_min = 0
            max_y = np.shape(psiArray[0])[1]
        for proc_num in xrange(processes):
#            x_min -= max_overlap
#            if x_min < 0:
#               x_min = 0
            x_max = x_min + (max_x/2)# 2*max_overlap + (max_x/2)
            xRangeProc = [x_min, x_max]
            yRangeProc = yRange
            xRangeList.append(xRangeProc)
            yRangeList.append(yRangeProc)
            x_min = x_max


        result = pool.map(self.findLikelyTrajectories, psiList,
                                                       phiList,
                                                       psfSigmaList,
                                                       vMaxList,
                                                       maxTimeStepList,
                                                       timeArrList,
                                                       xRangeList,
                                                       yRangeList,
                                                       numResultsList)
        # result = pool.map(self.testIt, [10])

        # keepT0, keepVel, keepScores, keepAlpha = result.get()
        total_result = [[], [], [], []]
        for entry in result:
            for col_num in range(len(entry)):
                total_result[col_num].append(entry[col_num])
        return total_result
        # return keepT0, keepVel, keepScores, keepAlpha

    def return_ra_dec(self, t0_pos, t0_vel, image_times, t0_mjd, wcs):

        pixel_vals = []
        for time_pt in image_times:
            pixel_vals.append(t0_pos + t0_vel*time_pt)
        pixel_vals = np.array(pixel_vals)
        coord_vals = astroCoords.SkyCoord.from_pixel(pixel_vals[:,0], pixel_vals[:,1], wcs)
        coord_list = coord_vals.to_string('hmsdms')
        output_list = []
        for coord_val, mjd in zip(coord_list, t0_mjd):
            coord_ra, coord_dec = coord_val.split(' ')
            ra_h = coord_ra.split('h')[0]
            ra_m = coord_ra.split('m')[0].split('h')[1]
            ra_s = coord_ra.split('s')[0].split('m')[1]
            dec_d = coord_dec.split('d')[0]
            dec_m = coord_dec.split('m')[0].split('d')[1]
            dec_s = coord_dec.split('s')[0].split('m')[1]
            output_list.append(str(str(mjd+2400000.5) + '  ' + '%s:%s:%s' + '  ' + '%s:%s:%s' +
                                   '  ' + '0.1  568') % (ra_h, ra_m, ra_s, dec_d, dec_m, dec_s))
        return np.array(output_list, dtype=str)

    def findObjectsEcliptic(self, psiArray, phiArray,
                            psfSigma, parallel_arr, perp_arr,
                            d_array, timeArr, wcs,
                            xRange=None, yRange=None, numResults=10):

        """
        parallel_arr: array with [min, max] values for angular Velocity
                      parallel to the ecliptic
        perp_arr: array with [min, max] values for angular Velocity
                  perpendicular to the ecliptic
        d_array: step size for [parallel, perpendicular] velocity grid
        """

        parallel_steps = np.arange(parallel_arr[0],
                                   parallel_arr[1] + d_array[0]/2.,
                                   d_array[0])
        perp_steps = np.arange(perp_arr[0],
                               perp_arr[1] + d_array[1]/2.,
                               d_array[1])
        vel_array = []
        for para_vel in parallel_steps:
            for perp_vel in perp_steps:
                vel_array.append([para_vel, perp_vel])
        vel_array = np.array(vel_array)

        psfPixelArea = np.pi*(psfSigma**2)
        tempResults = int(np.ceil(psfPixelArea)*numResults)*5

        topVel = np.zeros((tempResults, 2))
        topT0 = np.zeros((tempResults,2))
        topScores = np.zeros(tempResults)
        topAlpha = np.zeros(tempResults)
        if xRange is None:
            x_min = 0
            x_max = np.shape(psiArray[0])[0]
        else:
            x_min = xRange[0]
            x_max = xRange[1]
        if yRange is None:
            y_min = 0
            y_max = np.shape(psiArray[0])[1]
        else:
            y_min = yRange[0]
            y_max = yRange[1]
        for rowPos in xrange(x_min, x_max):
            print rowPos
            for colPos in xrange(y_min, y_max):
                objectStartArr = np.zeros((len(vel_array),2))
                objectStartArr[:,0] += rowPos
                objectStartArr[:,1] += colPos
                alphaArray, nuArray = self.calcAlphaNuEcliptic(psiArray,
                                                               phiArray,
                                                               objectStartArr,
                                                               vel_array,
                                                               timeArr,
                                                               wcs)
                for objNu, objAlpha, objVel in zip(nuArray, alphaArray, vel_array):
                    if objNu > np.min(topScores):
                        idx = np.argmin(topScores)
                        topScores[idx] = objNu
                        topT0[idx] = [rowPos, colPos]
                        topVel[idx] = objVel
                        topAlpha[idx] = objAlpha

        rankings = np.argsort(topScores)[-1::-1]
        keepVel = np.ones((numResults, 2)) * (999.) # To tell if it has been changed or not
        keepT0 = np.zeros((numResults, 2))
        keepScores = np.zeros(numResults)
        keepAlpha = np.zeros(numResults)

        resultsSet = 0
        for objNum in range(0,tempResults):
            testT0 = topT0[rankings][objNum]
            testVel = topVel[rankings][objNum]
            keepVal = True
            for t0, vel in zip(keepT0, keepVel):
                if ((euclidean(testT0, t0) <= psfSigma) and ((euclidean(testT0+(testVel*timeArr[-1]),
                                                                       t0+(vel*timeArr[-1])) <= psfSigma))):
                    keepVal=False
            if keepVal == True:
                keepT0[resultsSet] = testT0
                keepVel[resultsSet] = testVel
                keepScores[resultsSet] = topScores[rankings][objNum]
                keepAlpha[resultsSet] = topAlpha[rankings][objNum]
                resultsSet += 1
            if resultsSet == numResults:
                break
        print "\nTop %i results" %numResults
        print "Starting Positions: \n", keepT0
        print "Velocity Vectors: \n", keepVel
        print "Likelihood: \n", keepScores
        print "Best estimated flux: \n", keepAlpha

        return keepT0, keepVel, keepScores, keepAlpha

    def calcPixelLocationsFromEcliptic(self, pixel_start, vel_par, vel_perp,
                                       time_array, wcs):

        start_coord = astroCoords.SkyCoord.from_pixel(pixel_start[0],
                                                      pixel_start[1])
        eclip_coord = start_coord.geocentrictrueecliptic
        eclip_l = []
        eclip_b = []
        for time_step in time_array:
            eclip_l.append(eclip_coord.lon + vel_par*time_step*24.)
            eclip_b.append(eclip_coord.lat + vel_perp*time_step*24.)
        eclip_vector = astroCoords.SkyCoord(eclip_l, eclip_b,
                                            frame='geocentrictrueecliptic')
        pixel_coords = astroCoords.SkyCoord(eclip_vector, wcs)
        return pixel_coords

    def calcAlphaNuEcliptic(self, psiArray, phiArray,
                            objectStartArr, vel_array, timeArr, wcs):

        if len(np.shape(psiArray)) == 2:
            psiArray = [psiArray]
            phiArray = [phiArray]

        measureCoords = []
        for objNum in range(0, len(objectStartArr)):
            pixel_coords = self.calcPixelLocationsFromEcliptic(objectStartArr[objNum],
                                                               vel_array[objNum][0],
                                                               vel_array[objNum][1],
                                                               timeArr, wcs)
            measureCoords.append(pixel_coords)

        alphaMeasurements = []
        nuMeasurements = []
        for objNum in range(0, len(objectStartArr)):
            psiTotal = 0
            phiTotal = 0
            for imNum in range(0, len(psiArray)):
                try:
                    psiTotal += psiArray[imNum][measureCoords[objNum][0][imNum],
                                                measureCoords[objNum][1][imNum]]
                    phiTotal += phiArray[imNum][measureCoords[objNum][0][imNum],
                                                measureCoords[objNum][1][imNum]]
                except:
                    continue
            if (phiTotal != 0):
                alphaMeasurements.append(psiTotal/phiTotal)
                nuMeasurements.append(psiTotal/np.sqrt(phiTotal))
            else:
                alphaMeasurements.append(np.nan)
                nuMeasurements.append(np.nan)

        return alphaMeasurements, nuMeasurements
