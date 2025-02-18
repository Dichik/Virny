import numpy as np
import pandas as pd
import seaborn as sns

from os import listdir
from os.path import isfile, join
from matplotlib import pyplot as plt

from virny.configs.constants import CountPredictionStatsResponse
from virny.utils.data_viz_utils import set_size
from virny.metrics.stability_metrics import compute_std_mean_iqr_metrics, compute_entropy_from_predicted_probability,\
    compute_jitter, compute_per_sample_accuracy, compute_statistical_bias_from_predict_proba


def combine_bootstrap_predictions(bootstrap_predictions: dict, y_test_indexes: np.ndarray):
    """
    Combine predictions generated by estimators in the bootstrap to get final 1D array of predictions.

    Return a pandas series of predictions for each test sample.

    Parameters
    ----------
    bootstrap_predictions
        A dictionary where keys are indexes of bootstrap estimators and values are their predictions for the test set.
    y_test_indexes
        Indexes of the initial test set to keep original row indexes.

    """
    if isinstance(bootstrap_predictions, np.ndarray):
        results = pd.DataFrame(bootstrap_predictions)
    else:
        results = pd.DataFrame(bootstrap_predictions).transpose()

    main_prediction = results.mean().values
    y_preds = np.array([int(x<0.5) for x in main_prediction])

    return pd.Series(y_preds, index=y_test_indexes)


def count_prediction_stats(y_test, uq_results):
    """
    Compute means, stds, iqr, entropy, jitter, label stability, and transform predictions to pd.Dataframe.

    Return a 1D numpy array of predictions, 2D array of each model prediction for y_test, a data structure of metrics.

    Parameters
    ----------
    y_test
        True labels
    uq_results
        2D array of prediction proba for the zero value label by each model

    """
    if isinstance(uq_results, np.ndarray):
        results = pd.DataFrame(uq_results)
    else:
        results = pd.DataFrame(uq_results).transpose()

    means_lst, stds_lst, iqr_lst = compute_std_mean_iqr_metrics(results)
    mean_ensemble_entropy_lst = results.apply(compute_entropy_from_predicted_probability).mean().values

    # Convert predict proba results of each model to correspondent labels.
    # Here we use int(x<0.5) since we use predict_prob()[:, 0] to make predictions.
    # Hence, if a value is, for example, 0.3 --> label == 1, 0.6 -- > label == 0
    uq_labels = results.applymap(lambda x: int(x<0.5))
    jitter = compute_jitter(uq_labels.values)

    main_prediction = results.mean().values
    statistical_bias_lst = np.array(
        [compute_statistical_bias_from_predict_proba(x, y_true) for x, y_true in np.column_stack((main_prediction, y_test))]
    )
    overall_entropy_lst = np.array([compute_entropy_from_predicted_probability(x) for x in main_prediction])

    y_preds = np.array([int(x<0.5) for x in main_prediction])

    per_sample_accuracy_lst, label_stability_lst = compute_per_sample_accuracy(y_test, results)
    prediction_stats = CountPredictionStatsResponse(jitter=jitter,
                                                    means_lst=means_lst,
                                                    stds_lst=stds_lst,
                                                    iqr_lst=iqr_lst,
                                                    mean_ensemble_entropy_lst=mean_ensemble_entropy_lst,
                                                    overall_entropy_lst=overall_entropy_lst,
                                                    statistical_bias_lst=statistical_bias_lst,
                                                    per_sample_accuracy_lst=per_sample_accuracy_lst,
                                                    label_stability_lst=label_stability_lst)

    return y_preds, uq_labels, prediction_stats


def generate_bootstrap(features, labels, boostrap_size, with_replacement=True):
    bootstrap_index = np.random.choice(features.shape[0], size=boostrap_size, replace=with_replacement)
    bootstrap_features = pd.DataFrame(features).iloc[bootstrap_index].values
    bootstrap_labels = pd.DataFrame(labels).iloc[bootstrap_index].values
    if len(bootstrap_features) == boostrap_size:
        return bootstrap_features, bootstrap_labels
    else:
        raise ValueError('Bootstrap samples are not of the size requested')


def display_result_plots(results_dir):
    sns.set_style("darkgrid")
    results = dict()
    filenames = [f for f in listdir(results_dir) if isfile(join(results_dir, f))]

    for filename in filenames:
        results_df = pd.read_csv(results_dir + filename)
        results[f'{results_df.iloc[0]["Base_Model_Name"]}_{results_df.iloc[0]["N_Estimators"]}_estimators'] = results_df

    y_metrics = ['SPD_Race', 'SPD_Sex', 'SPD_Race_Sex', 'EO_Race', 'EO_Sex', 'EO_Race_Sex']
    x_metrics = ['Label_Stability', 'Std']
    for x_metric in x_metrics:
        for y_metric in y_metrics:
            x_lim = 0.3 if x_metric == 'SD' else 1.0
            display_uncertainty_plot(results, x_metric, y_metric, x_lim)


def display_uncertainty_plot(results, x_metric, y_metric, x_lim):
    fig, ax = plt.subplots()
    set_size(15, 8, ax)

    # List of all markers -- https://matplotlib.org/stable/api/markers_api.html
    markers = ['.', 'o', '+', '*', '|', '<', '>', '^', 'v', '1', 's', 'x', 'D', 'P', 'H']
    techniques = results.keys()
    shapes = []
    for idx, technique in enumerate(techniques):
        a = ax.scatter(results[technique][x_metric], results[technique][y_metric], marker=markers[idx], s=100)
        shapes.append(a)

    plt.axhline(y=0.0, color='r', linestyle='-')
    plt.xlabel(x_metric)
    plt.ylabel(y_metric)
    plt.xlim(0, x_lim)
    plt.title(f'{x_metric} [{y_metric}]', fontsize=20)
    ax.legend(shapes, techniques, fontsize=12, title='Markers')

    plt.show()
