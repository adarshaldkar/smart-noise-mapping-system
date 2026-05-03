import logging
import numpy as np
import librosa
import urllib.request
import csv
import io

try:
    import tensorflow as tf
    import tensorflow_hub as hub
except ImportError:
    tf = None
    hub = None
    logging.warning("TensorFlow is not installed. ML Classification will be disabled.")

# YAMNet model constants
YAMNET_MODEL_HANDLE = 'https://tfhub.dev/google/yamnet/1'
yamnet_model = None
class_names = []

def load_yamnet_model():
    """Loads the pre-trained Google YAMNet model from TensorFlow Hub"""
    global yamnet_model, class_names
    
    if tf is None or hub is None:
        return False
        
    if yamnet_model is None:
        try:
            logging.info(f"Loading YAMNet audio classification model from {YAMNET_MODEL_HANDLE}...")
            yamnet_model = hub.load(YAMNET_MODEL_HANDLE)
            logging.info("YAMNet model loaded successfully. Reading class mappings...")
            
            # Find the class map CSV file embedded in the model
            class_map_path = yamnet_model.class_map_path().numpy().decode('utf-8')
            
            with tf.io.gfile.GFile(class_map_path) as csvfile:
                reader = csv.DictReader(csvfile)
                class_names = [row['display_name'] for row in reader]
                
            logging.info(f"Loaded {len(class_names)} distinct sound classes (e.g., Traffic, Human Voice, Siren).")
            return True
        except Exception as e:
            logging.error(f"Failed to load YAMNet ML Model: {e}")
            return False
    return True

def classify_audio(audio_array, original_sr=44100):
    """
    Analyzes an audio array using the YAMNet Machine Learning model to determine the sound type.
    
    Args:
        audio_array: A 1D mono numpy array representing the audio wave.
        original_sr: The sample rate of the audio (default from moviepy is often 44100).
        
    Returns:
        tuple: (top_class_name, confidence_score) or (None, 0.0) if it fails.
    """
    if not load_yamnet_model():
        return None, 0.0
        
    try:
        # YAMNet STRICTLY requires 16 kHz mono audio to work. 
        if original_sr != 16000:
            logging.info(f"Resampling audio for ML from {original_sr}Hz to 16000Hz...")
            audio_array = librosa.resample(y=audio_array.astype(np.float32), orig_sr=original_sr, target_sr=16000)
            
        # Transform array values to be inside the interval [-1.0, 1.0] (Normalization)
        max_val = np.max(np.abs(audio_array))
        if max_val > 0 and max_val > 1.0:
            audio_array = audio_array / max_val
            
        # Run the intelligence model (Inference)!
        logging.info("Running ML Audio Classification...")
        scores, embeddings, spectrogram = yamnet_model(audio_array)
        
        # YAMNet returns scores per 0.48-second frames. Average them across the whole clip.
        class_scores = tf.reduce_mean(scores, axis=0)
        
        # Find the highest scoring class
        top_class_id = tf.argmax(class_scores).numpy()
        confidence = float(class_scores[top_class_id].numpy())
        top_class_name = class_names[top_class_id]
        
        logging.info(f"ML PREDICTION: '{top_class_name}' with {confidence*100:.1f}% confidence.")
        return top_class_name, confidence
        
    except Exception as e:
        logging.error(f"ML Classification Error: {e}")
        return None, 0.0
