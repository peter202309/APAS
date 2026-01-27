import pandas as pd
import io

def test_csv_loading():
    print("🧪 Testing CSV Loading...")
    
    csv_path = "c:\\Antigravity\\APAS\\batch_template.csv"
    try:
        df = pd.read_csv(csv_path)
        print(f"✅ Loaded CSV with {len(df)} rows.")
        print("Columns:", df.columns.tolist())
        
        for i, (_, row) in enumerate(df.iterrows()):
            print(f"\n--- Processing Row {i} ---")
            print(f"Origin: {row.get('origin')}, Destination: {row.get('destination')}")
            
            try:
                # Mirroring main.py logic
                trip_type=row.get('trip_type', 'round_trip')
                origin=row.get('origin')
                destination=row.get('destination')
                start_date=str(row.get('start_date'))
                
                # Check critical fields
                if pd.isna(origin) or pd.isna(destination):
                    print(f"❌ Row {i} has NaN origin or destination!")
                    continue

                # Check nights parsing
                nights_raw = row.get('nights', 7)
                nights = int(float(nights_raw)) if pd.notna(nights_raw) else 7
                print(f"✅ Row {i} parsed successfully. Nights: {nights}")
                
            except Exception as e:
                print(f"🔥 Row {i} parsing FAILED: {e}")
                
    except Exception as e:
        print(f"🔥 Failed to load CSV: {e}")

if __name__ == "__main__":
    test_csv_loading()
