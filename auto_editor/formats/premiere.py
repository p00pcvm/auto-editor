'''premiere.py'''

import os
from shutil import move

from auto_editor.formats.utils import fix_url, indent, get_width_height, safe_mkdir

def speedup(speed):
    return indent(6, '<filter>', '\t<effect>', '\t\t<name>Time Remap</name>',
        '\t\t<effectid>timeremap</effectid>',
        '\t\t<effectcategory>motion</effectcategory>',
        '\t\t<effecttype>motion</effecttype>',
        '\t\t<mediatype>video</mediatype>',
        '\t\t<parameter authoringApp="PremierePro">',
        '\t\t\t<parameterid>variablespeed</parameterid>',
        '\t\t\t<name>variablespeed</name>', '\t\t\t<valuemin>0</valuemin>',
        '\t\t\t<valuemax>1</valuemax>',
        '\t\t\t<value>0</value>',
        '\t\t</parameter>',
        '\t\t<parameter authoringApp="PremierePro">',
        '\t\t\t<parameterid>speed</parameterid>',  '\t\t\t<name>speed</name>',
        '\t\t\t<valuemin>-100000</valuemin>', '\t\t\t<valuemax>100000</valuemax>',
        '\t\t\t<value>{}</value>'.format(speed),
        '\t\t</parameter>',
        '\t\t<parameter authoringApp="PremierePro">',
        '\t\t\t<parameterid>reverse</parameterid>',
        '\t\t\t<name>reverse</name>', '\t\t\t<value>FALSE</value>',
        '\t\t</parameter>',
        '\t\t<parameter authoringApp="PremierePro">',
        '\t\t\t<parameterid>frameblending</parameterid>',
        '\t\t\t<name>frameblending</name>', '\t\t\t<value>FALSE</value>',
        '\t\t</parameter>', '\t</effect>', '</filter>')

def premiere_xml(inp, temp, output, clips, chunks, sampleRate, audioFile,
    resolve, fps, log):

    duration = chunks[len(chunks) - 1][1]
    pathurl = fix_url(inp.path, resolve)

    tracks = len(inp.audio_streams)
    name = inp.name

    log.debug('tracks: {}'.format(tracks))
    log.debug(inp.dirname)

    if(tracks > 1):
        name_without_extension = inp.basename[:inp.basename.rfind('.')]

        fold = safe_mkdir(os.path.join(inp.dirname, f'{name_without_extension}_tracks'))

        trackurls = [pathurl]
        for i in range(1, tracks):
            newtrack = os.path.join(fold, f'{i}.wav')
            move(os.path.join(temp, f'{i}.wav'), newtrack)
            trackurls.append(fix_url(newtrack, resolve))

    ntsc = 'FALSE'
    ana = 'FALSE' # anamorphic
    depth = '16'

    width, height = get_width_height(inp)

    pixelar = 'square' # pixel aspect ratio
    colordepth = '24'
    sr = sampleRate
    timebase = str(int(fps))

    if(audioFile):
        groupName = 'Auto-Editor Audio Group'
        with open(output, 'w', encoding='utf-8') as outfile:
            outfile.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
            outfile.write('<xmeml version="4">\n')
            outfile.write('\t<sequence>\n')
            outfile.write(f'\t\t<name>{groupName}</name>\n')
            outfile.write(f'\t\t<duration>{duration}</duration>\n')
            outfile.write('\t\t<rate>\n')
            outfile.write(f'\t\t\t<timebase>{timebase}</timebase>\n')
            outfile.write(f'\t\t\t<ntsc>{ntsc}</ntsc>\n')
            outfile.write('\t\t</rate>\n')
            outfile.write('\t\t<media>\n')

            outfile.write(indent(3, '<video>', '\t<format>',
                '\t\t<samplecharacteristics>',
                f'\t\t\t<width>{width}</width>',
                f'\t\t\t<height>{height}</height>',
                f'\t\t\t<pixelaspectratio>{pixelar}</pixelaspectratio>',
                '\t\t\t<rate>',
                f'\t\t\t\t<timebase>{timebase}</timebase>',
                f'\t\t\t\t<ntsc>{ntsc}</ntsc>',
                '\t\t\t</rate>',
                '\t\t</samplecharacteristics>',
                '\t</format>', '</video>'))

            outfile.write(indent(3, '<audio>',
                '\t<numOutputChannels>2</numOutputChannels>', '\t<format>',
                '\t\t<samplecharacteristics>',
                '\t\t\t<depth>{}</depth>'.format(depth),
                '\t\t\t<samplerate>{}</samplerate>'.format(sr),
                '\t\t</samplecharacteristics>',
                '\t</format>'))

            outfile.write('\t\t\t\t<track currentExplodedTrackIndex="0" premiereTrackType="Stereo">\n')

            total = 0
            for j, clip in enumerate(clips):
                myStart = int(total)
                total += (clip[1] - clip[0]) / (clip[2] / 100)
                myEnd = int(total)

                outfile.write(indent(5, f'<clipitem id="clipitem-{j+1}">',
                    '\t<masterclipid>masterclip-1</masterclipid>',
                    '\t<name>{}</name>'.format(inp.name),
                    '\t<start>{}</start>'.format(myStart),
                    '\t<end>{}</end>'.format(myEnd),
                    f'\t<in>{int(clip[0] / (clip[2] / 100))}</in>',
                    f'\t<out>{int(clip[1] / (clip[2] / 100))}</out>'))

                if(j == 0):
                    # Define file-1
                    outfile.write(indent(6, '<file id="file-1">',
                        f'\t<name>{inp.name}</name>',
                        f'\t<pathurl>{pathurl}</pathurl>',
                        '\t<rate>',
                        f'\t\t<timebase>{timebase}</timebase>',
                        f'\t\t<ntsc>{ntsc}</ntsc>',
                        '\t</rate>',
                        '\t<media>',
                        '\t\t<audio>',
                        '\t\t\t<samplecharacteristics>',
                        f'\t\t\t\t<depth>{depth}</depth>',
                        f'\t\t\t\t<samplerate>{sr}</samplerate>',
                        '\t\t\t</samplecharacteristics>',
                        '\t\t\t<channelcount>2</channelcount>',
                        '\t\t</audio>', '\t</media>', '</file>'))
                else:
                    outfile.write('\t\t\t\t\t\t<file id="file-1"/>\n')
                outfile.write('\t\t\t\t\t\t<sourcetrack>\n')
                outfile.write('\t\t\t\t\t\t\t<mediatype>audio</mediatype>\n')
                outfile.write('\t\t\t\t\t\t\t<trackindex>1</trackindex>\n')
                outfile.write('\t\t\t\t\t\t</sourcetrack>\n')
                outfile.write('\t\t\t\t\t</clipitem>\n')

            outfile.write('\t\t\t\t</track>\n')
            outfile.write('\t\t\t</audio>\n')
            outfile.write('\t\t</media>\n')
            outfile.write('\t</sequence>\n')
            outfile.write('</xmeml>')

            # Exit out of this function prematurely.
            return None

    groupName = 'Auto-Editor Video Group'

    with open(output, 'w', encoding='utf-8') as outfile:
        outfile.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
        outfile.write('<xmeml version="4">\n')
        outfile.write('\t<sequence>\n')
        outfile.write(f'\t\t<name>{groupName}</name>\n')
        outfile.write('\t\t<rate>\n')
        outfile.write(f'\t\t\t<timebase>{timebase}</timebase>\n')
        outfile.write(f'\t\t\t<ntsc>{ntsc}</ntsc>\n')
        outfile.write('\t\t</rate>\n')
        outfile.write('\t\t<media>\n')

        outfile.write(indent(3, '<video>', '\t<format>',
            '\t\t<samplecharacteristics>',
            '\t\t\t<rate>',
            f'\t\t\t\t<timebase>{timebase}</timebase>',
            f'\t\t\t\t<ntsc>{ntsc}</ntsc>',
            '\t\t\t</rate>',
            f'\t\t\t<width>{width}</width>',
            f'\t\t\t<height>{height}</height>',
            f'\t\t\t<anamorphic>{ana}</anamorphic>',
            f'\t\t\t<pixelaspectratio>{pixelar}</pixelaspectratio>',
            '\t\t\t<fielddominance>none</fielddominance>',
            f'\t\t\t<colordepth>{colordepth}</colordepth>',
            '\t\t</samplecharacteristics>',
            '\t</format>',
            '\t<track>'))

        # Handle clips.
        total = 0
        for j, clip in enumerate(clips):
            myStart = int(total)
            total += (clip[1] - clip[0]) / (clip[2] / 100)
            myEnd = int(total)

            outfile.write(indent(5, f'<clipitem id="clipitem-{j+1}">',
                '\t<masterclipid>masterclip-2</masterclipid>',
                f'\t<name>{inp.name}</name>',
                f'\t<start>{myStart}</start>',
                f'\t<end>{myEnd}</end>',
                f'\t<in>{int(clip[0] / (clip[2] / 100))}</in>',
                f'\t<out>{int(clip[1] / (clip[2] / 100))}</out>'))

            if(j == 0):
                outfile.write(indent(6, '<file id="file-1">',
                    f'\t<name>{inp.name}</name>',
                    f'\t<pathurl>{pathurl}</pathurl>',
                    '\t<rate>',
                    f'\t\t<timebase>{timebase}</timebase>',
                    f'\t\t<ntsc>{ntsc}</ntsc>',
                    '\t</rate>',
                    f'\t<duration>{duration}</duration>',
                    '\t<media>', '\t\t<video>',
                    '\t\t\t<samplecharacteristics>',
                    '\t\t\t\t<rate>',
                    f'\t\t\t\t\t<timebase>{timebase}</timebase>',
                    f'\t\t\t\t\t<ntsc>{ntsc}</ntsc>',
                    '\t\t\t\t</rate>',
                    f'\t\t\t\t<width>{width}</width>',
                    f'\t\t\t\t<height>{height}</height>',
                    f'\t\t\t\t<anamorphic>{ana}</anamorphic>',
                    f'\t\t\t\t<pixelaspectratio>{pixelar}</pixelaspectratio>',
                    '\t\t\t\t<fielddominance>none</fielddominance>',
                    '\t\t\t</samplecharacteristics>',
                    '\t\t</video>', '\t\t<audio>',
                    '\t\t\t<samplecharacteristics>',
                    f'\t\t\t\t<depth>{depth}</depth>',
                    f'\t\t\t\t<samplerate>{sr}</samplerate>',
                    '\t\t\t</samplecharacteristics>',
                    '\t\t\t<channelcount>2</channelcount>',
                    '\t\t</audio>', '\t</media>', '</file>'))
            else:
                outfile.write('\t\t\t\t\t\t<file id="file-1"/>\n')

            if(clip[2] != 100):
                outfile.write(speedup(clip[2]))

            # Linking for video blocks
            for i in range(max(3, tracks + 1)):
                outfile.write('\t\t\t\t\t\t<link>\n')
                outfile.write(f'\t\t\t\t\t\t\t<linkclipref>clipitem-{(i*(len(clips)))+j+1}</linkclipref>\n')
                if(i == 0):
                    outfile.write('\t\t\t\t\t\t\t<mediatype>video</mediatype>\n')
                else:
                    outfile.write('\t\t\t\t\t\t\t<mediatype>audio</mediatype>\n')
                if(i == 2):
                    outfile.write('\t\t\t\t\t\t\t<trackindex>2</trackindex>\n')
                else:
                    outfile.write('\t\t\t\t\t\t\t<trackindex>1</trackindex>\n')
                outfile.write(f'\t\t\t\t\t\t\t<clipindex>{j+1}</clipindex>\n')
                if(i > 0):
                    outfile.write('\t\t\t\t\t\t\t<groupindex>1</groupindex>\n')
                outfile.write('\t\t\t\t\t\t</link>\n')

            outfile.write('\t\t\t\t\t</clipitem>\n')

        # End Video; Start Audio
        outfile.write(indent(3, '\t</track>', '</video>', '<audio>',
            '\t<numOutputChannels>2</numOutputChannels>',
            '\t<format>',
            '\t\t<samplecharacteristics>',
            f'\t\t\t<depth>{depth}</depth>',
            f'\t\t\t<samplerate>{sr}</samplerate>',
            '\t\t</samplecharacteristics>',
            '\t</format>'))

        # Audio Clips
        for t in range(tracks):
            if(t == 0):
                print('')
            log.debug('t variable: ' + str(t))
            total = 0
            outfile.write('\t\t\t\t<track currentExplodedTrackIndex="0" premiereTrackType="Stereo">\n')

            for j, clip in enumerate(clips):

                clipItemNum = len(clips) + 1 + j + (t * len(clips))

                outfile.write(f'\t\t\t\t\t<clipitem id="clipitem-{clipItemNum}" premiereChannelType="stereo">\n')
                outfile.write('\t\t\t\t\t\t<masterclipid>masterclip-2</masterclipid>\n')
                outfile.write(f'\t\t\t\t\t\t<name>{name}</name>\n')

                myStart = int(total)
                total += (clip[1] - clip[0]) / (clip[2] / 100)
                myEnd = int(total)

                outfile.write(f'\t\t\t\t\t\t<start>{myStart}</start>\n')
                outfile.write(f'\t\t\t\t\t\t<end>{myEnd}</end>\n')

                outfile.write(f'\t\t\t\t\t\t<in>{int(clip[0] / (clip[2] / 100))}</in>\n')
                outfile.write(f'\t\t\t\t\t\t<out>{int(clip[1] / (clip[2] / 100))}</out>\n')

                if(t > 0):
                    # Define arbitrary file
                    outfile.write(indent(6, f'<file id="file-{t+1}">',
                        f'\t<name>{name}{t}</name>',
                        f'\t<pathurl>{trackurls[t]}</pathurl>',
                        '\t<rate>',
                        f'\t\t<timebase>{timebase}</timebase>',
                        f'\t\t<ntsc>{ntsc}</ntsc>',
                        '\t</rate>',
                        '\t<media>',
                        '\t\t<audio>',
                        '\t\t\t<samplecharacteristics>',
                        f'\t\t\t\t<depth>{depth}</depth>',
                        f'\t\t\t\t<samplerate>{sr}</samplerate>',
                        '\t\t\t</samplecharacteristics>',
                        '\t\t\t<channelcount>2</channelcount>',
                        '\t\t</audio>', '\t</media>', '</file>'))
                else:
                    outfile.write(f'\t\t\t\t\t\t<file id="file-{t+1}"/>\n')
                outfile.write('\t\t\t\t\t\t<sourcetrack>\n')
                outfile.write('\t\t\t\t\t\t\t<mediatype>audio</mediatype>\n')
                outfile.write('\t\t\t\t\t\t\t<trackindex>1</trackindex>\n')
                outfile.write('\t\t\t\t\t\t</sourcetrack>\n')
                outfile.write('\t\t\t\t\t\t<labels>\n')
                outfile.write('\t\t\t\t\t\t\t<label2>Iris</label2>\n')
                outfile.write('\t\t\t\t\t\t</labels>\n')

                # Add speed effect for audio blocks
                if(clip[2] != 100):
                    outfile.write(speedup(clip[2]))

                outfile.write('\t\t\t\t\t</clipitem>\n')
            outfile.write('\t\t\t\t\t<outputchannelindex>1</outputchannelindex>\n')
            outfile.write('\t\t\t\t</track>\n')

        outfile.write('\t\t\t</audio>\n')
        outfile.write('\t\t</media>\n')
        outfile.write('\t</sequence>\n')
        outfile.write('</xmeml>\n')

    log.conwrite('')
