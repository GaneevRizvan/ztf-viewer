import requests
import pandas as pd
from ztf_viewer.cache import cache

class ModelFit:
    base_url = f"http://host.docker.internal:8000/api/v1"
    bright_fit = "diffflux_Jy"
    brighterr_fit = "difffluxerr_Jy"

    def __init__(self):
        self._api_session = requests.Session()

    def fit(self, df, fit_model):
        path = f"/sncosmo/fit"
        res_fit = requests.post(self.base_url + path,
                                json={'light_curve': [{'mjd': float(mjd), 'flux': float(br), 'fluxerr': float(br_err),
                                                       "zp": 8.9, "zpsys": "ab", 'band': 'ztf' + str(band[1:])} for
                                                      br, mjd, br_err, band
                                                      in zip(df[self.bright_fit], df["mjd"], df[self.brighterr_fit], df["filter"])],
                                      'ebv': 0.03, 'name_model': fit_model, 'redshift': [0.05, 0.3]})
        params = res_fit.json()['parameters']
        return params

    @cache()
    def get_curve(self, params, name_model, band_ref, bright, band_list, mjd_min, mjd_max):
        path = f"/sncosmo/get_curve"
        res_fit = requests.post(self.base_url + path, json={'parameters': params, 'name_model': name_model, "zp": 8.9, "zpsys": "ab",
                                           'band_list': band_list,
                                           't_min': mjd_min, 't_max': mjd_max,
                                           'count': 2000, 'brightness_type': bright, 'band_ref': band_ref})
        return pd.DataFrame.from_records(res_fit.json()['bright'])

    def models(self):
        path = f"/models"
        list_models = requests.get(self.base_url + path).json()['models']
        return list_models

model_fit = ModelFit()