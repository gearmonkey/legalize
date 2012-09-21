# encoding: utf-8
import os
import simplejson
from operator import itemgetter
from urllib import quote as urlquote

import mmpy
import spotimeta
import pyechonest.song

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

p2p_diff = None
metacache = {}
metadata = spotimeta.Metadata(cache=metacache)

def fetch_top_N_albums(topN, spotify=True):
    by_album = fetch_top_N_by_rel_type(topN, 'album', spotify)
    max_rank = by_album[-1][0]
    by_mixtape = fetch_top_N_by_rel_type(topN, 'mixtape', spotify=spotify, max_rank=max_rank)
    return sorted(by_album+by_mixtape, key=itemgetter(0))[:topN]
    
def fetch_top_N_by_rel_type(topN, rel_type, spotify=True, max_rank=None):
    mapped = []
    for rank, val, relgrp in p2p_diff.releasegroup:
        if max_rank != None and rank > max_rank:
            break
        try:
            if rel_type in relgrp.description.lower():
                if spotify:
                    res = metadata.search_album(relgrp.artist.name+' '+relgrp.name)
                    mapped.append((rank, val, res['result'][0]))
                else:
                    mapped.append((rank, val, {'name':relgrp.name, 'artist':{'name':relgrp.artist.name}}))
        except IndexError:
            print "no album found for "+relgrp.name+" by "+relgrp.artist.name
            continue
        if len(mapped) >= topN:
            break
    return mapped
    
def ideal_pair(request):
    """given either a song and an album, or two albums, determine the pair with the minimum timbrel distance, using echonest timbrel features (actually just random seleciton for the moment)"""
    itemA = request.matchdict['itemA']
    itemB = request.matchdict['itemB']
    feature = request.matchdict.get('feature', 'danceability')
    
    if 'spotify:album' in itemA:
        #doing two way timbrel analysis
        full_album_detail = metadata.lookup(itemA, detail=2)
        songs_A = []
        for song in full_album_detail['result']['tracks']:
            try:
                res = pyechonest.song.search(title=song['name'], 
                                             artist=song['artist']['name'], 
                                             buckets="audio_summary")[0]
            except IndexError:
                print "couldn't get features for",song['name'],"by", song['artist']
                continue
            songs_A.append((song["href"], res.audio_summary[feature]))
    else:
        song = metadata.lookup(itemA)['result']
        res = pyechonest.song.search(title=song['name'], 
                                     artist=song['artist']['name'], 
                                     buckets="audio_summary")[0]
        songs_A = [(song["href"], res.audio_summary[feature])]

    songs_B = []
    full_album_detail = metadata.lookup(itemB, detail=2)
    for song in full_album_detail['result']['tracks']:
        try:
            res = pyechonest.song.search(title=song['name'], 
                                         artist=song['artist']['name'], 
                                         buckets="audio_summary")[0]
        except IndexError:
            print u"couldn't get features for",song['name'].encode('utf8'),
            print u"by", song['artist']['name'].encode('utf8')
            continue
        songs_B.append((song["href"], res.audio_summary[feature]))
    min_dist = abs(songs_A[0][1]-songs_B[0][1])
    songA = songs_A[0]
    songB = songs_B[0]
    for idx,(uriA,feature_valueA) in enumerate(songs_A):
        for jdx,(uriB,feature_valueB) in enumerate(songs_B):
            if abs(feature_valueA-feature_valueB) < min_dist:
                songA = songs_A[idx]
                songB = songs_B[jdx]
          
    return Response(simplejson.dumps({'response':[songA, songB]}), content_type='application/json',
                    headers={'Access-Control-Allow-Origin':'*',
                             'Access-Control-Request-Headers': 'x-requested-with',
                             'Access-Control-Allow-Methods':'GET'})
        
def topN(request):
    albums = fetch_top_N_albums(int(request.matchdict.get('topN', 10)))
    album_chart = u'<br/>'.join([u'Nº{rank}: <a href="{uri}">{album} by {artist}</a> with {peers} unique peers today.'.format(rank=rank, uri=album['href'], 
               album=album['name'].encode('utf8'),
               artist=album['artist']['name'], 
               peers=val) for rank, val, album in albums])
    doc_body = u'''<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" 
    "http://www.w3.org/TR/html4/strict.dtd">

<html lang="en">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <title>Popular Albums on Bittorrent -- Resolved to Spotify</title>
        <meta name="author" content="Benjamin Fields">
    </head>
    <body>
        <a href="https://github.com/gearmonkey/legalize"><img style="position: absolute; top: 0; left: 0; border: 0;" src="https://s3.amazonaws.com/github/ribbons/forkme_left_green_007200.png" alt="Fork me on GitHub"></a>
        <div class="chart" style="margin:10px auto 10px auto; width:800px">
            <h2 style="text-align:center;">Popular Albums on Bittorrent -- Resolved to Spotify</h2>
            <br />
            '''+album_chart+'''
            </div>
            <div id="footer" style="position:fixed;bottom:0;width:100%">
                <a href="http://developer.echoest.com"><img src="http://the.echonest.com/media/images/logos/EN_P_on_Black.gif" style="float:left;margin-bottom:6px;"/></a>
                <a href="http://developer.musicmetric.com"><img src="http://developer.musicmetric.com/_static/musicmetric.png" style="float:right; background-color:#484848; padding:4px; margin-right:30px; margin-top:6px;" /></a>
            </div>
        
    </body>
</html>
    '''
    return Response(doc_body)
    
def tomahkN(request):
    rel_type = request.matchdict.get('rel_type', 10).rstrip('s')
    if rel_type == 'album':
        releases = fetch_top_N_albums(int(request.matchdict.get('topN', 10)), spotify=False)
        chart = u'<br/>'.join([u'''Nº{rank} on the {rel_type} chart, with {peers} unique peers today:<br/>
            <iframe src="http://toma.hk/album/{artist}/{release}?embed=true" 
            width="550" height="430" scrolling="no" frameborder="0" allowtransparency="true" ></iframe>'''.format(rank=idx+1, 
                                                release=urlquote(album['name'].encode('utf8')),
                                                artist=urlquote(album['artist']['name']), 
                                                peers=val, rel_type=rel_type) for idx, (rank, val, album) in enumerate(releases)])
    else:
        releases = fetch_top_N_by_rel_type(int(request.matchdict.get('topN', 10)), rel_type, spotify=False)
        chart = u'<br/>'.join([u'''Nº{rank} on the {rel_type} chart, with {peers} unique peers today:<br/>
        <iframe src="http://toma.hk/embed.php?artist={artist}&title={release}" 
        width="200" scrolling="no" height="200" frameborder="0" allowtransparency="true" ></iframe>'''.format(rank=idx+1, 
                                                release=urlquote(album['name'].encode('utf8')),
                                                artist=urlquote(album['artist']['name']), 
                                                peers=val, rel_type=rel_type) for idx, (rank, val, album) in enumerate(releases)])
    doc_body = u'''<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" 
    "http://www.w3.org/TR/html4/strict.dtd">

<html lang="en">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <title>Popular Albums Today on Bittorrent -- Resolved via tomahawk</title>
        <meta name="author" content="Benjamin Fields">
    </head>
    <body>
        <a href="https://github.com/gearmonkey/legalize"><img style="position: absolute; top: 0; left: 0; border: 0;" src="https://s3.amazonaws.com/github/ribbons/forkme_left_green_007200.png" alt="Fork me on GitHub"></a>
        <div class="chart" style="margin:10px auto 10px auto; width:800px">
            <h2 style="text-align:center;">Popular {rel_type} Today on Bittorrent -- Resolved via <a href="http://toma.hk/" target=_BLANK>tomahawk</a></h2>
            <br />
            '''+chart+'''
            </div>
            <div id="footer" style="position:fixed;bottom:0;width:100%">
                <a href="http://developer.echoest.com"><img src="http://the.echonest.com/media/images/logos/EN_P_on_Black.gif" style="float:left;margin-bottom:6px;"/></a>
                <a href="http://developer.musicmetric.com"><img src="http://developer.musicmetric.com/_static/musicmetric.png" style="float:right; background-color:#484848; padding:4px; margin-right:30px; margin-top:6px;" /></a>
            </div>

    </body>
</html>
    '''
    doc_body.format(rel_type=rel_type+'s')
    return Response(doc_body)
    
def topNjson(request):
    albums = fetch_top_N_albums(int(request.matchdict.get('topN', 10)))
    return Response(simplejson.dumps({'response':albums}, indent="  "), content_type='application/json', 
                    headers={'Access-Control-Allow-Origin':'*',
                             'Access-Control-Request-Headers': 'x-requested-with',
                             'Access-Control-Allow-Methods':'GET'})

if __name__ == '__main__':
    config = Configurator()
    config.add_route('index', '')
    config.add_route('topjson', '/top/{topN}.json')
    config.add_route('top', '/top/{topN}')
    config.add_route('paired', '/paired/{itemA}/{itemB}')
    config.add_route('pairedby', '/paired/{itemA}/{itemB}/{feature}')
    #tomahawk routes
    config.add_route('tomahkN', '/tomahkN/{rel_type}/{topN}')
    
    config.add_view(topN, route_name='top')
    config.add_view(topN, route_name='index')
    config.add_view(topNjson, route_name='topjson')
    config.add_view(ideal_pair, route_name='paired')
    config.add_view(ideal_pair, route_name='pairedby')
    config.add_view(tomahkN, route_name='tomahkN')
    
    port = int(os.environ.get('PORT', 5000))
    app = config.make_wsgi_app()
    server = make_server('0.0.0.0', port, app)
    print 'made server'
    p2p_diff = mmpy.Chart('p2p daily releasegroups')
    print 'fetched chart'
    server.serve_forever()