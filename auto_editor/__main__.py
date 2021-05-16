#!/usr/bin/env python3
'''__main__.py'''

# Internal Libraries
import os
import sys
import tempfile
from shutil import rmtree

version = '21w19b dev'

def error(message):
    print('Error!', message, file=sys.stderr)
    sys.exit(1)

def file_type(file: str) -> str:
    if(not os.path.isfile(file)):
        error('Auto-Editor could not find the file: ' + file)
    return file

def float_type(num: str) -> float:
    if(num.endswith('%')):
        return float(num[:-1]) / 100
    return float(num)

def sample_rate_type(num: str) -> int:
    if(num.endswith(' Hz')):
        return int(num[:-3])
    if(num.endswith(' kHz')):
        return int(float(num[:-4]) * 1000)
    if(num.endswith('kHz')):
        return int(float(num[:-3]) * 1000)
    if(num.endswith('Hz')):
        return int(num[:-2])
    return int(num)

def frame_type(inp: str):
    if(inp.endswith('sec')):
        return inp[:-3]
    if(inp.endswith('secs')):
        return inp[:-4]
    return int(inp)

def comma_type(inp: str, min_args=1, max_args=None, name='') -> list:
    from usefulFunctions import cleanList
    inp = cleanList(inp.split(','), '\r\n\t')
    if(min_args > len(inp)):
        error(f'Too few comma arguments for {name}.')
    if(max_args is not None and len(inp) > max_args):
        error(f'Too many comma arguments for {name}.')
    return inp

def zoom_type(inp):
    return comma_type(inp, 3, 8, 'zoom_type')

def rect_type(inp):
    return comma_type(inp, 6, 8, 'rect_type')

def range_type(inp):
    return comma_type(inp, 2, 2, 'range_type')

def speed_range_type(inp):
    return comma_type(inp, 3, 3, 'speed_range_type')


def appendFileName(file_name, val):
    dotIndex = file_name.rfind('.')
    end = val + file_name[dotIndex:]
    return file_name[:dotIndex] + end

# Pad so that the av method works.
def padChunk(item, totalFrames):
    start = None
    end = None
    if(item[0] != 0):
        start = [0, item[0], 2]
    if(item[1] != totalFrames -1):
        end = [item[1], totalFrames -1, 2]

    if(start is None):
        return [item] + [end]
    if(end is None):
        return [start] + [item]
    return [start] + [item] + [end]

def main_options(parser):
    parser.add_argument('urlOps', nargs=0, action='grouping')
    parser.add_argument('--format', type=str, group='urlOps',
        default='bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        help='the format youtube-dl uses to when downloading a url.')
    parser.add_argument('--output_dir', type=str, group='urlOps',
        default=None,
        help='the directory where the downloaded file is placed.')
    parser.add_argument('--check_certificate', action='store_true', group='urlOps',
        help='check the website certificate before downloading.')

    parser.add_argument('progressOps', nargs=0, action='grouping')
    parser.add_argument('--machine_readable_progress', action='store_true',
        group='progressOps',
        help='set progress bar that is easier to parse.')
    parser.add_argument('--no_progress', action='store_true',
        group='progressOps',
        help='do not display any progress at all.')

    parser.add_argument('metadataOps', nargs=0, action='grouping')
    parser.add_argument('--force_fps_to', type=float, group='metadataOps',
        help='manually set the fps value for the input video if detection fails.')
    parser.add_argument('--force_tracks_to', type=int, group='metadataOps',
        help='manually set the number of tracks auto-editor thinks there are.')

    parser.add_argument('exportMediaOps', nargs=0, action='grouping')
    parser.add_argument('--video_bitrate', '-vb', default='unset', group='exportMediaOps',
        help='set the number of bits per second for video.')
    parser.add_argument('--audio_bitrate', '-ab', default='unset', group='exportMediaOps',
        help='set the number of bits per second for audio.')
    # parser.add_argument('--video_quality', '-')
    parser.add_argument('--sample_rate', '-r', type=sample_rate_type,
        group='exportMediaOps',
        help='set the sample rate of the input and output videos.')
    parser.add_argument('--video_codec', '-vcodec', default='copy',
        group='exportMediaOps',
        help='set the video codec for the output media file.')
    parser.add_argument('--audio_codec', '-acodec', group='exportMediaOps',
        help='set the audio codec for the output media file.')
    parser.add_argument('--preset', '-p', default='medium', group='exportMediaOps',
        choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium',
            'slow', 'slower', 'veryslow'],
        help='set the preset for ffmpeg to help save file size or increase quality.')
    parser.add_argument('--tune', '-t', default='none', group='exportMediaOps',
        choices=['film', 'animation', 'grain', 'stillimage', 'fastdecode',
            'zerolatency', 'none', 'unset'],
        help='set the tune for ffmpeg to compress video better in certain circumstances.')
    parser.add_argument('--constant_rate_factor', '-crf', type=int, default=15,
        group='exportMediaOps', range='0 to 51',
        help='set the quality for video using the crf method.')

    parser.add_argument('motionOps', nargs=0, action='grouping')
    parser.add_argument('--dilates', '-d', type=int, default=2, range='0 to 5',
        group='motionOps',
        help='set how many times a frame is dilated before being compared.')
    parser.add_argument('--width', '-w', type=int, default=400, range='1 to Infinity',
        group='motionOps',
        help="scale the frame to this width before being compared.")
    parser.add_argument('--blur', '-b', type=int, default=21, range='0 to Infinity',
        group='motionOps',
        help='set the strength of the blur applied to a frame before being compared.')

    parser.add_argument('--export_as_audio', '-exa', action='store_true',
        help='export as a WAV audio file.')
    parser.add_argument('--export_to_premiere', '-exp', action='store_true',
        help='export as an XML file for Adobe Premiere Pro instead of outputting a media file.')
    parser.add_argument('--export_to_resolve', '-exr', action='store_true',
        help='export as an XML file for DaVinci Resolve instead of outputting a media file.')
    parser.add_argument('--export_to_final_cut_pro', '-exf', action='store_true',
        help='export as an XML file for Final Cut Pro instead of outputting a media file.')
    parser.add_argument('--export_as_json', action='store_true',
        help='export as a JSON file that can be read by auto-editor later.')
    parser.add_argument('--export_as_clip_sequence', '-excs', action='store_true',
        help='export as multiple numbered media files.')

    parser.add_argument('--render', default='auto', choices=['av', 'opencv', 'auto'],
        help='choice which method to render video.')
    parser.add_argument('--scale', type=float_type, default=1,
        help='scale the output media file by a certian factor.')

    parser.add_argument('--zoom', type=zoom_type, nargs='*',
        help='set when and how a zoom will occur.',
        extra='The arguments are: start,end,start_zoom,end_zoom,x,y,inter,hold' \
            '\nThere must be at least 3 comma args. x and y default to centerX and centerY' \
            '\nThe default interpolation is linear.')
    parser.add_argument('--rectangle', type=rect_type, nargs='*',
        help='overlay a rectangle shape on the video.',
        extra='The arguments are: start,end,x1,y1,x2,y2,color,thickness' \
            '\nThere must be at least 6 comma args. The rectangle is solid if' \
            ' thickness is not defined.\n The default color is #000.')

    parser.add_argument('--background', type=str, default='#000',
        help='set the color of the background that is visible when the video is moved.')

    parser.add_argument('--mark_as_loud', type=range_type, nargs='*',
        help='the range that will be marked as "loud".')
    parser.add_argument('--mark_as_silent', type=range_type, nargs='*',
        help='the range that will be marked as "silent".')
    parser.add_argument('--cut_out', type=range_type, nargs='*',
        help='the range of media that will be removed completely, regardless of the value of silent speed.')
    parser.add_argument('--set_speed_for_range', type=speed_range_type, nargs='*',
        help='set an arbitrary speed for a given range.',
        extra='The arguments are: speed,start,end')

    parser.add_argument('--motion_threshold', type=float_type, default=0.02,
        range='0 to 1',
        help='how much motion is required to be considered "moving"')
    parser.add_argument('--edit_based_on', default='audio',
        choices=['audio', 'motion', 'not_audio', 'not_motion', 'audio_or_motion',
            'audio_and_motion', 'audio_xor_motion', 'audio_and_not_motion',
            'not_audio_and_motion', 'not_audio_and_not_motion'],
        help='decide which method to use when making edits.')

    parser.add_argument('--cut_by_this_audio', '-ca', type=file_type,
        help="base cuts by this audio file instead of the video's audio.")
    parser.add_argument('--cut_by_this_track', '-ct', type=int, default=0,
        range='0 to the number of audio tracks minus one',
        help='base cuts by a different audio track in the video.')
    parser.add_argument('--cut_by_all_tracks', '-cat', action='store_true',
        help='combine all audio tracks into one before basing cuts.')
    parser.add_argument('--keep_tracks_seperate', action='store_true',
        help="don't combine audio tracks when exporting.")

    parser.add_argument('--my_ffmpeg', action='store_true',
        help='use your ffmpeg and other binaries instead of the ones packaged.')
    parser.add_argument('--version', action='store_true',
        help='show which auto-editor you have.')
    parser.add_argument('--debug', '--verbose', '-d', action='store_true',
        help='show debugging messages and values.')
    parser.add_argument('--show_ffmpeg_debug', action='store_true',
        help='show ffmpeg progress and output.')
    parser.add_argument('--quiet', '-q', action='store_true',
        help='display less output.')

    parser.add_argument('--combine_files', action='store_true',
        help='combine all input files into one before editing.')
    parser.add_argument('--preview', action='store_true',
        help='show stats on how the input will be cut.')
    parser.add_argument('--no_open', action='store_true',
        help='do not open the file after editing is done.')
    parser.add_argument('--min_clip_length', '-mclip', type=frame_type, default=3,
        range='0 to Infinity',
        help='set the minimum length a clip can be. If a clip is too short, cut it.')
    parser.add_argument('--min_cut_length', '-mcut', type=frame_type, default=6,
        range='0 to Infinity',
        help="set the minimum length a cut can be. If a cut is too short, don't cut")

    parser.add_argument('--output_file', '--output', '-o', nargs='*',
        help='set the name(s) of the new output.')
    parser.add_argument('--silent_threshold', '-t', type=float_type, default=0.04,
        range='0 to 1',
        help='set the volume that frames audio needs to surpass to be "loud".')
    parser.add_argument('--silent_speed', '-s', type=float_type, default=99999,
        range='Any number. Values <= 0 or >= 99999 will be cut out.',
        help='set the speed that "silent" sections should be played at.')
    parser.add_argument('--video_speed', '--sounded_speed', '-v', type=float_type,
        default=1.00,
        range='Any number. Values <= 0 or >= 99999 will be cut out.',
        help='set the speed that "loud" sections should be played at.')
    parser.add_argument('--frame_margin', '-m', type=frame_type, default=6,
        range='0 to Infinity',
        help='set how many "silent" frames of on either side of "loud" sections be included.')

    parser.add_argument('--help', '-h', action='store_true',
        help='print info about the program or an option and exit.')
    parser.add_argument('(input)', nargs='*',
        help='the path to a file, folder, or url you want edited.')
    return parser


def main():
    dirPath = os.path.dirname(os.path.realpath(__file__))
    # Fixes pip not able to find other included modules.
    sys.path.append(os.path.abspath(dirPath))

    import vanparse

    parser = vanparse.ArgumentParser('Auto-Editor', version,
        description='\nAuto-Editor is an automatic video/audio creator and editor. '\
            'By default, it will detect silence and create a new video with those '\
            'sections cut out. By changing some of the options, you can export to a '\
            'traditional editor like Premiere Pro and adjust the edits there, adjust '\
            'the pacing of the cuts, and change the method of editing like using audio '\
            'loudness and video motion to judge making cuts.\nRun:\n    auto-editor '\
            '--help\n\nTo get the list of options.\n')

    parser.add_argument('--help', '-h', action='store_true',
        help='print info about the program or an option and exit.')

    from usefulFunctions import Log, Timer, isLatestVersion, fNone, sep
    from ffwrapper import FFmpeg, FFprobe

    subcommands = ['create', 'test', 'info', 'levels']

    if(len(sys.argv) > 1 and sys.argv[1] in subcommands):
        if(sys.argv[1] == 'create'):
            from create import create, create_options
            parser = create_options(parser)
            args = parser.parse_args(sys.argv[2:], Log(), 'create')

            ffmpeg = FFmpeg(dirPath, args.my_ffmpeg, True, Log())
            create(ffmpeg, args.input, args.output_file, args.frame_rate, args.duration,
                args.width, args.height, Log())

        if(sys.argv[1] == 'test'):
            from testAutoEditor import testAutoEditor
            testAutoEditor()

        if(sys.argv[1] == 'info'):
            from info import getInfo, info_options
            parser = info_options(parser)
            args = parser.parse_args(sys.argv[2:], Log(), 'info')

            log = Log()
            ffmpeg = FFmpeg(dirPath, args.my_ffmpeg, False, log)
            ffprobe = FFprobe(dirPath, args.my_ffmpeg, False, log)
            getInfo(args.input, ffmpeg, ffprobe, args.fast, log)
        if(sys.argv[1] == 'levels'):
            from levels import levels, levels_options
            parser = levels_options(parser)
            args = parser.parse_args(sys.argv[2:], Log(), 'levels')

            TEMP = tempfile.mkdtemp()
            log = Log(temp=TEMP)
            ffmpeg = FFmpeg(dirPath, args.my_ffmpeg, False, log)
            ffprobe = FFprobe(dirPath, args.my_ffmpeg, False, log)
            levels(args.input, args.track, args.output_file, ffmpeg, ffprobe, TEMP, log)
        sys.exit()
    else:
        parser = main_options(parser)
        args = parser.parse_args(sys.argv[1:], Log(True), 'auto-editor')

    timer = Timer(args.quiet)

    ffmpeg = FFmpeg(dirPath, args.my_ffmpeg, args.show_ffmpeg_debug, Log())
    ffprobe = FFprobe(dirPath, args.my_ffmpeg, args.show_ffmpeg_debug, Log())

    # Stops "The file {file} does not exist." from showing.
    if(args.export_as_clip_sequence):
        args.no_open = True

    makingDataFile = (args.export_to_premiere or args.export_to_resolve or
        args.export_to_final_cut_pro or args.export_as_json)
    is64bit = '64-bit' if sys.maxsize > 2**32 else '32-bit'

    if(args.debug and args.input == []):
        import platform

        print('Python Version:', platform.python_version(), is64bit)
        print('Platform:', platform.system(), platform.release())
        print('Config File path:', dirPath + sep() + 'config.txt')
        print('FFmpeg path:', ffmpeg.getPath())
        print('FFmpeg version:', ffmpeg.getVersion())
        print('Auto-Editor version', version)
        sys.exit()

    TEMP = tempfile.mkdtemp()
    log = Log(args.debug, args.quiet, temp=TEMP)
    log.debug(f'\n   - Temp Directory: {TEMP}')

    if(is64bit == '32-bit'):
        log.warning('You have the 32-bit version of Python, which may lead to' \
            'memory crashes.')

    if(args.version):
        print('Auto-Editor version', version)
        sys.exit()

    ffmpeg.updateLog(log)
    ffprobe.updateLog(log)

    if(not args.quiet and not isLatestVersion(version, log)):
        log.print('\nAuto-Editor is out of date. Run:\n')
        log.print('    pip3 install -U auto-editor')
        log.print('\nto upgrade to the latest version.\n')

    from argsCheck import hardArgsCheck, softArgsCheck
    hardArgsCheck(args, log)
    args = softArgsCheck(args, log)

    from validateInput import validInput
    inputList = validInput(args.input, ffmpeg, args, log)

    # Figure out the output file names.
    def newOutputName(oldFile: str, audio, final_cut_pro, data, json) -> str:
        dotIndex = oldFile.rfind('.')
        print(oldFile)
        if(json):
            return oldFile[:dotIndex] + '.json'
        if(final_cut_pro):
            return oldFile[:dotIndex] + '.fcpxml'
        if(data):
            return oldFile[:dotIndex] + '.xml'
        if(audio):
            return oldFile[:dotIndex] + '_ALTERED.wav'
        return oldFile[:dotIndex] + '_ALTERED' + oldFile[dotIndex:]

    if(len(args.output_file) < len(inputList)):
        for i in range(len(inputList) - len(args.output_file)):
            args.output_file.append(newOutputName(inputList[i],
                args.export_as_audio, args.export_to_final_cut_pro, makingDataFile,
                args.export_as_json))

    if(args.combine_files):
        # Combine video files, then set input to 'combined.mp4'.
        cmd = []
        for fileref in inputList:
            cmd.extend(['-i', fileref])
        cmd.extend(['-filter_complex', f'[0:v]concat=n={len(inputList)}:v=1:a=1',
            '-codec:v', 'h264', '-pix_fmt', 'yuv420p', '-strict', '-2',
            f'{TEMP}{sep()}combined.mp4'])
        ffmpeg.run(cmd)
        del cmd
        inputList = [f'{TEMP}{sep()}combined.mp4']

    speeds = [args.silent_speed, args.video_speed]
    if(args.cut_out != [] and 99999 not in speeds):
        speeds.append(99999)

    for item in args.set_speed_for_range:
        if(item[0] not in speeds):
            speeds.append(float(item[0]))

    log.debug(f'   - Speeds: {speeds}')

    from wavfile import read
    audioExtensions = ['.wav', '.mp3', '.m4a', '.aiff', '.flac', '.ogg', '.oga',
        '.acc', '.nfa', '.mka']
    sampleRate = None

    for i, INPUT_FILE in enumerate(inputList):

        if(len(inputList) > 1):
            log.conwrite(f'Working on {INPUT_FILE}')

        fileFormat = INPUT_FILE[INPUT_FILE.rfind('.'):]

        chunks = None
        if(fileFormat == '.json'):
            log.debug('Reading .json file')
            from makeCutList import readCutList
            INPUT_FILE, chunks, speeds = readCutList(INPUT_FILE, version, log)
            newOutput = newOutputName(INPUT_FILE, args.export_as_audio,
                args.export_to_final_cut_pro, makingDataFile, False)

            fileFormat = INPUT_FILE[INPUT_FILE.rfind('.'):]
        else:
            newOutput = args.output_file[i]
            if(not os.path.isdir(INPUT_FILE) and '.' not in newOutput):
                newOutput += INPUT_FILE[INPUT_FILE.rfind('.'):]

        log.debug(f'   - INPUT_FILE: {INPUT_FILE}')
        log.debug(f'   - newOutput: {newOutput}')

        if(os.path.isfile(newOutput) and INPUT_FILE != newOutput):
            log.debug(f'  Removing already existing file: {newOutput}')
            os.remove(newOutput)

        if(args.sample_rate is None):
            sampleRate = ffprobe.getSampleRate(INPUT_FILE)
            if(sampleRate == 'N/A'):
                sampleRate = '48000'
                log.warning(f"Samplerate wasn't detected, so it will be set to {sampleRate}.")
        else:
            sampleRate = str(args.sample_rate)
        log.debug(f'   - sampleRate: {sampleRate}')

        if(args.audio_bitrate is None):
            if(INPUT_FILE.endswith('.mkv')):
                # audio bitrate not supported in the mkv container.
                audioBitrate = None
            else:
                audioBitrate = ffprobe.getPrettyBitrate(INPUT_FILE, 'a')
                if(audioBitrate == 'N/A'):
                    log.warning("Couldn't automatically detect audio bitrate.")
                    audioBitrate = None
        else:
            audioBitrate = args.audio_bitrate

        log.debug(f'   - audioBitrate: {audioBitrate}')

        audioData = None
        audioFile = fileFormat in audioExtensions
        if(audioFile):
            if(args.force_fps_to is None):
                fps = 30 # Audio files don't have frames, so give fps a dummy value.
            else:
                fps = args.force_fps_to
            if(args.force_tracks_to is None):
                tracks = 1
            else:
                tracks = args.force_tracks_to
            cmd = ['-i', INPUT_FILE]
            if(not fNone(audioBitrate)):
                cmd.extend(['-b:a', audioBitrate])
            cmd.extend(['-ac', '2', '-ar', sampleRate, '-vn', f'{TEMP}{sep()}fastAud.wav'])
            ffmpeg.run(cmd)
            del cmd

            sampleRate, audioData = read(f'{TEMP}{sep()}fastAud.wav')
        else:
            if(args.force_fps_to is not None):
                fps = args.force_fps_to
            elif(args.export_to_premiere or args.export_to_final_cut_pro or
                args.export_to_resolve):
                # Based on timebase.
                fps = int(ffprobe.getFrameRate(INPUT_FILE))
            else:
                fps = ffprobe.getFrameRate(INPUT_FILE)

            if(fps < 1):
                log.error(f"{INPUT_FILE}: Frame rate cannot be below 1. fps: {fps}")

            tracks = args.force_tracks_to
            if(tracks is None):
                tracks = ffprobe.getAudioTracks(INPUT_FILE)

            if(args.cut_by_this_track >= tracks):
                allTracks = ''
                for trackNum in range(tracks):
                    allTracks += f'Track {trackNum}\n'

                if(tracks == 1):
                    message = f'is only {tracks} track'
                else:
                    message = f'are only {tracks} tracks'
                log.error("You choose a track that doesn't exist.\n" \
                    f'There {message}.\n {allTracks}')

            def NumberOfVrfFrames(text, log):
                import re
                search = re.search(r'VFR:[\d.]+ \(\d+\/\d+\)', text, re.M)
                if(search is None):
                    log.warning('Could not get number of VRF Frames.')
                    return 0
                else:
                    nums = re.search(r'\d+\/\d+', search.group()).group(0)
                    log.debug(nums)
                    return int(nums.split('/')[0])

            def hasVFR(cmd, log):
                return NumberOfVrfFrames(ffmpeg.pipe(cmd), log) != 0

            # Split audio tracks into: 0.wav, 1.wav, etc.
            cmd = ['-i', INPUT_FILE, '-hide_banner']
            for trackNum in range(tracks):
                cmd.extend(['-map', f'0:a:{trackNum}'])
                if(not fNone(audioBitrate)):
                    cmd.extend(['-ab', audioBitrate])
                cmd.extend(['-ac', '2', '-ar', sampleRate,
                    f'{TEMP}{sep()}{trackNum}.wav'])
            cmd.extend(['-map', '0:v:0', '-vf', 'vfrdet', '-f', 'null', '-'])
            has_vfr = hasVFR(cmd, log)
            del cmd

            # Check if the `--cut_by_all_tracks` flag has been set or not.
            if(args.cut_by_all_tracks):
                # Combine all audio tracks into one audio file, then read.
                cmd = ['-i', INPUT_FILE, '-filter_complex',
                    f'[0:a]amix=inputs={tracks}:duration=longest', '-ar',
                    sampleRate, '-ac', '2', '-f', 'wav', f'{TEMP}{sep()}combined.wav']
                ffmpeg.run(cmd)
                sampleRate, audioData = read(f'{TEMP}{sep()}combined.wav')
                del cmd
            else:
                # Read only one audio file.
                if(os.path.isfile(f'{TEMP}{sep()}{args.cut_by_this_track}.wav')):
                    sampleRate, audioData = read(f'{TEMP}{sep()}{args.cut_by_this_track}.wav')
                else:
                    log.bug('Audio track not found!')

        log.debug(f'   - Frame Rate: {fps}')
        if(chunks is None):
            from cutting import audioToHasLoud, motionDetection

            audioList = None
            motionList = None
            if('audio' in args.edit_based_on):
                log.debug('Analyzing audio volume.')
                audioList = audioToHasLoud(audioData, sampleRate,
                    args.silent_threshold,  fps, log)

            if('motion' in args.edit_based_on):
                log.debug('Analyzing video motion.')
                motionList = motionDetection(INPUT_FILE, ffprobe,
                    args.motion_threshold, log, width=args.width,
                    dilates=args.dilates, blur=args.blur)

                if(audioList is not None):
                    if(len(audioList) != len(motionList)):
                        log.debug(f'audioList Length:  {len(audioList)}')
                        log.debug(f'motionList Length: {len(motionList)}')
                    if(len(audioList) > len(motionList)):
                        log.debug('Reducing the size of audioList to match motionList.')
                        audioList = audioList[:len(motionList)]
                    elif(len(motionList) > len(audioList)):
                        log.debug('Reducing the size of motionList to match audioList.')
                        motionList = motionList[:len(audioList)]

            from cutting import combineArrs, applySpacingRules

            hasLoud = combineArrs(audioList, motionList, args.edit_based_on, log)
            del audioList, motionList

            effects = []
            if(args.zoom != []):
                from cutting import applyZooms
                effects += applyZooms(args.zoom, audioData, sampleRate, fps, log)
            if(args.rectangle != []):
                from cutting import applyRects
                effects += applyRects(args.rectangle, audioData, sampleRate, fps, log)

            chunks = applySpacingRules(hasLoud, speeds, fps, args, log)
            del hasLoud

        def isClip(chunk):
            nonlocal speeds
            return speeds[chunk[2]] != 99999

        def getNumberOfCuts(chunks, speeds):
            return len(list(filter(isClip, chunks)))

        def getClips(chunks, speeds):
            clips = []
            for chunk in chunks:
                if(isClip(chunk)):
                    clips.append([chunk[0], chunk[1], speeds[chunk[2]] * 100])
            return clips

        numCuts = getNumberOfCuts(chunks, speeds)
        clips = getClips(chunks, speeds)

        if(args.export_as_json):
            from makeCutList import makeCutList
            makeCutList(INPUT_FILE, newOutput, version, chunks, speeds, log)
            continue

        if(args.preview):
            newOutput = None
            from preview import preview
            preview(INPUT_FILE, chunks, speeds, fps, audioFile, log)
            continue

        if(args.export_to_premiere or args.export_to_resolve):
            from editor import editorXML
            editorXML(INPUT_FILE, TEMP, newOutput, ffprobe, clips, chunks, tracks,
                sampleRate, audioFile, args.export_to_resolve, fps, log)
            continue

        if(args.export_to_final_cut_pro):
            from editor import fcpXML
            fcpXML(INPUT_FILE, TEMP, newOutput, ffprobe, clips, chunks, tracks,
                sampleRate, audioFile, fps, log)
            continue

        def makeAudioFile(input_, chunks, output):
            from fastAudio import fastAudio, handleAudio, convertAudio
            theFile = handleAudio(ffmpeg, input_, audioBitrate, str(sampleRate),
                TEMP, log)

            TEMP_FILE = f'{TEMP}{sep()}convert.wav'
            fastAudio(theFile, TEMP_FILE, chunks, speeds, log, fps,
                args.machine_readable_progress, args.no_progress)
            convertAudio(ffmpeg, ffprobe, TEMP_FILE, input_, output, args, log)

        if(audioFile):
            if(args.export_as_clip_sequence):
                i = 1
                for item in chunks:
                    if(speeds[item[2]] == 99999):
                        continue
                    makeAudioFile(INPUT_FILE, [item], appendFileName(newOutput, f'-{i}'))
                    i += 1
            else:
                makeAudioFile(INPUT_FILE, chunks, newOutput)
            continue

        def makeVideoFile(input_, chunks, output):
            from videoUtils import handleAudioTracks, muxVideo
            continueVid = handleAudioTracks(ffmpeg, output, args, tracks, chunks, speeds,
                fps, TEMP, log)
            if(continueVid):
                if(args.render == 'auto'):
                    if(args.zoom != [] or args.rectangle != []):
                        args.render = 'opencv'
                    else:
                        try:
                            import av
                            args.render = 'av'
                        except ImportError:
                            args.render = 'opencv'

                log.debug(f'Using {args.render} method')
                if(args.render == 'av'):
                    if(args.zoom != []):
                        log.error('Zoom effect is not supported on the av render method.')

                    if(args.rectangle != []):
                        log.error('Rectangle effect is not supported on the av render method.')

                    from renderVideo import renderAv
                    renderAv(ffmpeg, ffprobe, input_, args, chunks, speeds, fps, has_vfr,
                        TEMP, log)

                if(args.render == 'opencv'):
                    from renderVideo import renderOpencv
                    renderOpencv(ffmpeg, ffprobe, input_, args, chunks, speeds, fps,
                        has_vfr, effects, TEMP, log)

                # Now mix new audio(s) and the new video.
                muxVideo(ffmpeg, output, args, tracks, TEMP, log)
                if(output is not None and not os.path.isfile(output)):
                    log.bug(f'The file {output} was not created.')

        if(args.export_as_clip_sequence):
            i = 1
            totalFrames = chunks[len(chunks) - 1][1]
            speeds.append(99999) # guarantee we have a cut speed to work with.
            for chunk in chunks:
                if(speeds[chunk[2]] == 99999):
                    continue

                makeVideoFile(INPUT_FILE, padChunk(chunk, totalFrames),
                    appendFileName(newOutput, f'-{i}'))
                i += 1
        else:
            makeVideoFile(INPUT_FILE, chunks, newOutput)

    if(not args.preview and not makingDataFile):
        timer.stop()

    if(not args.preview and makingDataFile):
        from usefulFunctions import humanReadableTime
        # Assume making each cut takes about 30 seconds.
        timeSave = humanReadableTime(numCuts * 30)

        s = 's' if numCuts != 1 else ''
        log.print(f'Auto-Editor made {numCuts} cut{s}', end='')
        log.print(f', which would have taken about {timeSave} if edited manually.')

    if(not args.no_open):
        from usefulFunctions import openWithSystemDefault
        openWithSystemDefault(newOutput, log)

    log.debug('Deleting temp dir')

    try:
        rmtree(TEMP)
    except PermissionError:
        from time import sleep
        sleep(1)
        try:
            rmtree(TEMP)
        except PermissionError:
            log.debug('Failed to delete temp dir.')

if(__name__ == '__main__'):
    main()
