# encoding: utf-8
import os
import simplejson

import mmpy
import spotimeta
import pyechonest.song

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

p2p_diff = None
metacache = {}
metadata = spotimeta.Metadata(cache=metacache)

def fetch_top_N_albums(topN):
    mapped = []
    for rank, val, relgrp in p2p_diff.releasegroup:
        try:
            if 'album' in relgrp.description.lower() or 'mixtape' in relgrp.description.lower():
                res = metadata.search_album(relgrp.artist.name+' '+relgrp.name)
                mapped.append((rank, val, res['result'][0]))
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
            print "couldn't get features for",song['name'],"by", song['artist']
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
                    headers={'Access-Control-Request-Headers': 'x-requested-with'})
        
def topN(request):
    albums = fetch_top_N_albums(int(request.matchdict.get('topN', 10)))
    doc_body = '<br/>'.join([u'no°{rank}: <a href="{uri}">{album} by {artist}</a> with {peers} unique peers today.'.format(rank=rank, uri=album['href'], 
               album=album['name'].encode('utf8'),
               artist=album['artist']['name'], 
               peers=val) for rank, val, album in albums])
    return Response(doc_body)
    
def topNjson(request):
    albums = fetch_top_N_albums(int(request.matchdict.get('topN', 10)))
    return Response(simplejson.dumps({'response':albums}, indent="  "), content_type='application/json', 
                    headers={'Access-Control-Request-Headers': 'x-requested-with'})

if __name__ == '__main__':
    config = Configurator()
    config.add_route('index', '')
    config.add_route('topjson', '/top/{topN}.json')
    config.add_route('top', '/top/{topN}')
    config.add_route('paired', '/paired/{itemA}/{itemB}')
    config.add_route('pairedby', '/paired/{itemA}/{itemB}/{feature}')
    
    config.add_view(topN, route_name='top')
    config.add_view(topN, route_name='index')
    config.add_view(topNjson, route_name='topjson')
    config.add_view(ideal_pair, route_name='paired')
    config.add_view(ideal_pair, route_name='pairedby')
    
    port = int(os.environ.get('PORT', 5000))
    app = config.make_wsgi_app()
    server = make_server('0.0.0.0', port, app)
    print 'made server'
    p2p_diff = mmpy.Chart('p2p daily releasegroups')
    print 'fetched chart'
    server.serve_forever()