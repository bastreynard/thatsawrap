"""
Transfer service for moving playlists between music services.
"""
from utils import set_progress


class TransferService:
    """Service for transferring playlists between music services."""
    
    def __init__(self, source_service, destination_service):
        """
        Initialize transfer service.
        
        Args:
            source_service: Source music service (e.g., SpotifyService)
            destination_service: Destination music service (e.g., TidalService)
        """
        self.source = source_service
        self.destination = destination_service
    
    def transfer_playlist(self, playlist_id, playlist_type, user_id):
        """
        Transfer a playlist from source to destination.
        
        Args:
            playlist_id: ID of the playlist to transfer
            playlist_type: Type of playlist ('playlist' or 'liked')
            user_id: User ID for progress tracking
            
        Returns:
            dict: Transfer results with success status and statistics
        """
        print(f'\n=== Starting playlist transfer ===')
        print(f'Playlist ID: {playlist_id}')
        print(f'Type: {playlist_type}')
        
        # Reset progress
        set_progress(user_id, 0, 0, 0, '')
        
        # Get tracks from source
        playlist_name, tracks = self.source.get_playlist_tracks(playlist_id, playlist_type)
        print(f'Found {len(tracks)} tracks to transfer')
        
        # Create destination playlist
        playlist_id_dest = self.destination.create_playlist(
            name=playlist_name,
            description=f'Transferred from {self.source.service_name.title()}'
        )
        
        # Transfer tracks
        added_count = 0
        not_found = []
        
        for idx, track in enumerate(tracks):
            if not track:
                continue
            
            # Update progress
            progress = int(((idx + 1) / len(tracks)) * 100)
            set_progress(user_id, progress, added_count, len(tracks))
            
            # Get track info
            track_name = track.get('name', '')
            artist_name = track['artists'][0]['name'] if track.get('artists') else ''
            
            # Refresh destination token periodically during long transfers
            if idx % 20 == 0:
                self.destination.get_valid_token()
            
            # Search for track on destination
            track_id = self.destination.search_track(track_name, artist_name)
            
            if track_id:
                # Add track to playlist
                success = self.destination.add_track_to_playlist(playlist_id_dest, track_id)
                
                if success:
                    added_count += 1
                    print(f'✓ Added: {track_name} - {artist_name}')
                else:
                    print(f'✗ Failed to add: {track_name} - {artist_name}')
                    not_found.append(f'{track_name} - {artist_name}')
            else:
                not_found.append(f'{track_name} - {artist_name}')
                print(f'✗ Not found: {track_name} - {artist_name}')
        
        # Final progress update
        set_progress(user_id, 100, added_count, len(tracks))
        
        print(f'\n=== Transfer complete ===')
        print(f'Added: {added_count}/{len(tracks)}')
        
        return {
            'success': added_count > 0,
            'playlist_name': playlist_name,
            'total_tracks': len(tracks),
            'tracks_added': added_count,
            'tracks_not_found': len(not_found),
            'not_found_list': not_found[:10]  # Return first 10 for display
        }
