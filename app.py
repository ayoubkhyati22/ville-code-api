from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import csv
import re
from datetime import datetime
import unicodedata
import difflib
from station_data import STATION_CODES
from station_aliases import STATION_ALIASES
from station_data_markoub import STATION_DATA_MARKOUB

app = Flask(__name__)
CORS(app)

class VilleCodeFinder:
    def __init__(self, data_path=None):
        """
        Initialise le système de recherche de codes ville

        Args:
            data_path: Chemin vers le fichier CSV contenant les villes du maroc et leurs codes
        """
        # Dictionnaire de base pour ONCF
        if data_path and data_path.endswith('.csv'):
            self.load_data_from_csv(data_path)
        else:
            # Exemple de données si aucun fichier n'est fourni
            self.data = STATION_CODES
            self.villes = list(self.data.keys())
        
        # Dictionnaire pour Markoub - conversion du format liste vers dictionnaire
        self.markoub_data = self.convert_markoub_data(STATION_DATA_MARKOUB)
        self.markoub_villes = list(self.markoub_data.keys())
        
        # Création du dictionnaire d'alias
        self.create_aliases()

    def convert_markoub_data(self, markoub_list):
        """
        Convertit les données Markoub du format liste vers dictionnaire
        
        Args:
            markoub_list: Liste des données Markoub
            
        Returns:
            dict: Dictionnaire {ville: code}
        """
        markoub_dict = {}
        
        if isinstance(markoub_list, list):
            for item in markoub_list:
                if isinstance(item, dict) and 'label' in item and 'value' in item:
                    # Normaliser le nom de la ville (minuscules)
                    ville_name = item['label'].lower()
                    markoub_dict[ville_name] = item['value']
                elif isinstance(item, dict) and 'meta' in item and 'value' in item:
                    # Format alternatif avec 'meta'
                    ville_name = item['meta'].lower()
                    markoub_dict[ville_name] = item['value']
        elif isinstance(markoub_list, dict):
            # Si c'est déjà un dictionnaire, on le retourne tel quel
            return {k.lower(): v for k, v in markoub_list.items()}
            
        return markoub_dict

    def load_data_from_csv(self, data_path):
        """
        Charge les données depuis un fichier CSV
        
        Args:
            data_path: Chemin vers le fichier CSV
        """
        self.data = {}
        with open(data_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                # Supposons que les colonnes sont 'ville' et 'code'
                self.data[row['ville'].lower()] = row['code']
        
        self.villes = list(self.data.keys())

    def save_data_to_csv(self, output_path):
        """
        Sauvegarde les données dans un fichier CSV
        
        Args:
            output_path: Chemin du fichier de sortie
        """
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['ville', 'code'])
            writer.writeheader()
            for ville in self.villes:
                writer.writerow({
                    'ville': ville,
                    'code': self.data[ville]
                })

    def create_aliases(self):
        """
        Crée un dictionnaire d'alias pour les villes
        """
        self.aliases = {}
        self.markoub_aliases = {}
        
        # Définir des alias communs
        common_aliases = STATION_ALIASES
        
        # Ajouter les alias prédéfinis pour ONCF
        for ville, liste_alias in common_aliases.items():
            for alias in liste_alias:
                if ville in self.data:  # On vérifie que la ville existe dans notre base
                    self.aliases[alias] = ville
        
        # Générer automatiquement des alias supplémentaires pour toutes les villes ONCF
        for ville in self.villes:
            self._generate_aliases_for_ville(ville, self.aliases, ville)
            
        # Générer des alias pour Markoub
        for ville in self.markoub_villes:
            self._generate_aliases_for_ville(ville, self.markoub_aliases, ville)

    def _generate_aliases_for_ville(self, ville, alias_dict, original_ville):
        """
        Génère des alias pour une ville donnée
        """
        # Suppression des accents
        alias_sans_accent = self.remove_accents(ville)
        if alias_sans_accent != ville:
            alias_dict[alias_sans_accent] = original_ville
        
        # Versions sans espace
        alias_sans_espace = ville.replace(" ", "")
        if alias_sans_espace != ville:
            alias_dict[alias_sans_espace] = original_ville
            
        # Première partie du nom (si composé)
        if " " in ville:
            premier_mot = ville.split(" ")[0]
            if len(premier_mot) > 2:  # On ne prend que les mots assez longs
                alias_dict[premier_mot] = original_ville
            
            # Dernière partie du nom
            dernier_mot = ville.split(" ")[-1]
            if len(dernier_mot) > 2:
                alias_dict[dernier_mot] = original_ville

    def remove_accents(self, text):
        """
        Supprime les accents d'une chaîne de caractères
        
        Args:
            text: Texte à nettoyer
            
        Returns:
            Texte sans accents
        """
        return ''.join(c for c in unicodedata.normalize('NFD', text)
                     if unicodedata.category(c) != 'Mn')

    def normalize_text(self, text):
        """
        Normalise un texte pour la recherche
        
        Args:
            text: Texte à normaliser
            
        Returns:
            Texte normalisé
        """
        if not text:
            return ""
            
        # Conversion en minuscules
        text = text.lower()
        
        # Suppression des accents
        text = self.remove_accents(text)
        
        # Suppression des caractères spéciaux
        text = re.sub(r'[^a-z0-9\s]', '', text)
        
        return text.strip()

    def levenshtein_distance(self, s1, s2):
        """
        Calcule la distance de Levenshtein entre deux chaînes
        
        Args:
            s1, s2: Chaînes à comparer
            
        Returns:
            distance: Distance de Levenshtein
        """
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def calculate_similarity(self, s1, s2):
        """
        Calcule la similarité entre deux chaînes
        
        Args:
            s1, s2: Chaînes à comparer
            
        Returns:
            score: Score de similarité entre 0 et 100
        """
        # Normalisation
        s1 = self.normalize_text(s1)
        s2 = self.normalize_text(s2)
        
        # Si la chaîne est exacte, score parfait
        if s1 == s2:
            return 100
            
        # Vérifie si une chaîne contient l'autre
        if s1 in s2:
            # Plus la différence de longueur est petite, plus le score est élevé
            return 90 - int(10 * (len(s2) - len(s1)) / len(s2))
        if s2 in s1:
            return 90 - int(10 * (len(s1) - len(s2)) / len(s1))
        
        # Vérifier les mots communs
        words1 = set(re.findall(r'\w+', s1))
        words2 = set(re.findall(r'\w+', s2))
        
        common_words_score = 0
        if words1 and words2:
            common = words1.intersection(words2)
            if common:
                common_words_score = int(70 * len(common) / max(len(words1), len(words2)))
        
        # Calcul de similarité avec difflib (séquence matcher)
        seq_similarity = int(difflib.SequenceMatcher(None, s1, s2).ratio() * 70)
        
        # Distance de Levenshtein
        if not s1 or not s2:
            levenshtein_score = 0
        else:
            max_len = max(len(s1), len(s2))
            if max_len == 0:
                levenshtein_score = 100
            else:
                distance = self.levenshtein_distance(s1, s2)
                levenshtein_score = int(70 * (1 - distance / max_len))
        
        # Retourner le meilleur score parmi toutes nos méthodes
        return max(common_words_score, seq_similarity, levenshtein_score)

    def find_code(self, ville_query, service='oncf', threshold=40):
        """
        Trouve le code d'une ville même avec des erreurs d'orthographe

        Args:
            ville_query: Nom de la ville à rechercher (peut être incomplet ou contenir des erreurs)
            service: Service à utiliser ('oncf' ou 'markoub')
            threshold: Seuil de similarité minimum (0-100)

        Returns:
            tuple: (code, score de similarité, nom exact de la ville)
        """
        if not ville_query:
            return None, 0, None
            
        ville_query = ville_query.lower()
        
        # Sélectionner les données appropriées selon le service
        if service == 'markoub':
            data = self.markoub_data
            villes = self.markoub_villes
            aliases = self.markoub_aliases
        else:
            data = self.data
            villes = self.villes
            aliases = self.aliases
        
        # 1. Recherche exacte d'abord
        if ville_query in data:
            return data[ville_query], 100, ville_query
            
        # 2. Vérification dans le dictionnaire d'alias
        normalized_query = self.normalize_text(ville_query)
        if normalized_query in aliases:
            original_ville = aliases[normalized_query]
            return data[original_ville], 95, original_ville
            
        # 3. Recherche de la chaîne dans les noms de villes
        for ville in villes:
            if normalized_query in self.normalize_text(ville):
                return data[ville], 90, ville
                
        # 4. Si aucune correspondance exacte, utiliser la recherche par similarité
        best_match = None
        best_score = 0
        
        for ville in villes:
            score = self.calculate_similarity(ville_query, ville)
            if score > best_score:
                best_score = score
                best_match = ville
        
        # Vérifier aussi parmi les alias pour la similarité
        for alias, ville in aliases.items():
            score = self.calculate_similarity(ville_query, alias)
            if score > best_score:
                best_score = score
                best_match = ville

        if best_match and best_score >= threshold:
            return data[best_match], best_score, best_match
        else:
            return None, 0, None


# Initialisation de l'API Flask
app = Flask(__name__)
CORS(app)  # Permet les requêtes cross-origin

# Création d'une instance de VilleCodeFinder
finder = VilleCodeFinder()

@app.route('/', methods=['GET'])
def index():
    """Page d'accueil avec documentation basique"""
    return """
    <h1>API VilleCodeFinder</h1>
    <p>Utilisez l'endpoint /api/find pour rechercher un code de ville</p>
    <p>Paramètres:</p>
    <ul>
        <li>departStation: Nom de la gare de départ</li>
        <li>arrivalStation: Nom de la gare d'arrivée</li>
    </ul>
    <p>Exemple: <a href="/api/find?departStation=casa&arrivalStation=rabat">/api/find?departStation=casa&arrivalStation=rabat</a></p>
    <p>Ou utilisez l'endpoint /api/booking pour obtenir un objet de réservation complet (ONCF + Markoub)</p>
    """

@app.route('/api/find', methods=['GET'])
def find_stations():
    """
    Endpoint pour trouver les codes des gares de départ et d'arrivée
    
    Query parameters:
        departStation: Nom de la gare de départ
        arrivalStation: Nom de la gare d'arrivée
    
    Returns:
        JSON avec les informations des deux gares pour ONCF et Markoub
    """
    depart = request.args.get('departStation', '')
    arrivee = request.args.get('arrivalStation', '')
    
    # Vérifier si les paramètres sont présents
    if not depart or not arrivee:
        return jsonify({
            "error": "Les paramètres 'departStation' et 'arrivalStation' sont requis"
        }), 400
    
    # Rechercher les codes des gares pour ONCF
    code_depart_oncf, score_depart_oncf, ville_depart_exacte_oncf = finder.find_code(depart, 'oncf')
    code_arrivee_oncf, score_arrivee_oncf, ville_arrivee_exacte_oncf = finder.find_code(arrivee, 'oncf')
    
    # Rechercher les codes des gares pour Markoub
    code_depart_markoub, score_depart_markoub, ville_depart_exacte_markoub = finder.find_code(depart, 'markoub')
    code_arrivee_markoub, score_arrivee_markoub, ville_arrivee_exacte_markoub = finder.find_code(arrivee, 'markoub')
    
    # Préparer la réponse
    response = {
        "oncf": {
            "depart": {
                "recherche": depart,
                "ville": ville_depart_exacte_oncf,
                "code": code_depart_oncf,
                "score": score_depart_oncf
            },
            "arrivee": {
                "recherche": arrivee,
                "ville": ville_arrivee_exacte_oncf,
                "code": code_arrivee_oncf,
                "score": score_arrivee_oncf
            }
        },
        "markoub": {
            "depart": {
                "recherche": depart,
                "ville": ville_depart_exacte_markoub,
                "code": code_depart_markoub,
                "score": score_depart_markoub
            },
            "arrivee": {
                "recherche": arrivee,
                "ville": ville_arrivee_exacte_markoub,
                "code": code_arrivee_markoub,
                "score": score_arrivee_markoub
            }
        }
    }
    
    return jsonify(response)

@app.route('/api/booking', methods=['GET'])
def booking_request():
    """
    Endpoint pour générer un objet de réservation au format demandé pour ONCF et Markoub
    
    Query parameters:
        departStation: Nom de la gare de départ 
        arrivalStation: Nom de la gare d'arrivée 
        comfort: Niveau de confort (optionnel)
        adults: Nombre d'adultes (optionnel)
        kids: Nombre d'enfants (optionnel)
        dateDepart: Date de départ (format YYYY-MM-DD)
        passengers: Nombre total de passagers pour Markoub (optionnel)
        
    Returns:
        JSON avec l'objet de réservation formaté pour ONCF et Markoub
    """
    # Récupérer les paramètres
    depart = request.args.get('departStation', '')
    arrivee = request.args.get('arrivalStation', '')
    comfort = request.args.get('comfort', '2')
    adults = request.args.get('adults', '1')
    kids = request.args.get('kids', '0')
    passengers = request.args.get('passengers', '1')
    date_str = request.args.get('dateDepart', None)
    
    # Rechercher les codes des gares pour ONCF
    code_depart_oncf, _, _ = finder.find_code(depart, 'oncf')
    code_arrivee_oncf, _, _ = finder.find_code(arrivee, 'oncf')
    
    # Rechercher les codes des gares pour Markoub
    code_depart_markoub, _, _ = finder.find_code(depart, 'markoub')
    code_arrivee_markoub, _, _ = finder.find_code(arrivee, 'markoub')
    
    # Préparer la date de départ
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            departure_date = date_obj.strftime("%Y-%m-%dT10:00:00+01:00")
            markoub_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            # Utiliser la date actuelle si le format est incorrect
            departure_date = datetime.now().strftime("%Y-%m-%dT10:00:00+01:00")
            markoub_date = datetime.now().strftime("%Y-%m-%d")
    else:
        departure_date = datetime.now().strftime("%Y-%m-%dT10:00:00+01:00")
        markoub_date = datetime.now().strftime("%Y-%m-%d")
    
    # Préparer la réponse ONCF
    oncf_response = {
        "codeGareDepart": code_depart_oncf,
        "codeGareArrivee": code_arrivee_oncf,
        "codeNiveauConfort": int(comfort),
        "dateDepartAller": departure_date,
        "dateDepartAllerMax": None, 
        "dateDepartRetour": None,
        "dateDepartRetourMax": None,
        "isTrainDirect": None,
        "isPreviousTrainAller": None,
        "isTarifReduit": True,
        "adulte": int(adults),
        "kids": int(kids),
        "listVoyageur": [
            {
                "numeroClient": None,
                "codeTarif": None,
                "codeProfilDemographique": "3",
                "dateNaissance": None
            }
        ],
        "booking": False,
        "isEntreprise": False,
        "token": "",
        "numeroContract": "",
        "codeTiers": ""
    }
    
    # Ajouter des voyageurs supplémentaires si nécessaire pour ONCF
    total_passengers = int(adults) + int(kids)
    if total_passengers > 1:
        for _ in range(1, total_passengers):
            oncf_response["listVoyageur"].append({
                "numeroClient": None,
                "codeTarif": None,
                "codeProfilDemographique": "3",
                "dateNaissance": None
            })
    
    # Préparer la réponse Markoub
    markoub_response = {
        "0": {
            "json": {
                "arrivalCityId": code_arrivee_markoub,
                "departureCityId": code_depart_markoub,
                "date": markoub_date,
                "nbrOfPassengers": int(passengers),
                "searchType": "direct"
            }
        }
    }
    
    # Réponse combinée
    response = {
        "oncf": oncf_response,
        "markoub": markoub_response
    }
    
    return jsonify(response)

@app.route('/api/villes', methods=['GET'])
def list_villes():
    """
    Endpoint pour lister toutes les villes disponibles pour ONCF et Markoub
    
    Returns:
        JSON avec la liste des villes et leurs codes pour les deux services
    """
    oncf_villes = [{"ville": ville, "code": finder.data[ville]} for ville in finder.villes]
    markoub_villes = [{"ville": ville, "code": finder.markoub_data[ville]} for ville in finder.markoub_villes]
    
    response = {
        "oncf": oncf_villes,
        "markoub": markoub_villes
    }
    
    return jsonify(response)

if __name__ == "__main__":
    # Définir le port à partir de la variable d'environnement PORT ou utiliser 5000 par défaut
    port = int(os.environ.get("PORT", 5000))
    # Démarrer le serveur en mode debug pour le développement
    app.run(host="0.0.0.0", port=port, debug=True)