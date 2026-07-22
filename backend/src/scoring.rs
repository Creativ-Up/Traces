use crate::{
    artworks::{Artwork, Artworks, ResultArtwork},
    emotions::Emotions,
    types_of_object::TypesOfObject,
};
use anyhow::{Context, Result, anyhow};
use std::{
    iter::Sum,
    ops::{Add, Div},
};

const OWA_WEIGHTS: &[f64] = &[0.125, 0.125, 0.125, 0.625];

pub fn proposals_from_history(history: &[i64]) -> Result<Vec<ResultArtwork>> {
    if history.is_empty() {
        return Err(anyhow!("empty history"));
    }
    let artworks = Artworks::read_all().context("while retrieving artworks")?;
    let artworks_history = artworks
        .iter()
        .filter(|a| history.contains(&a.id()))
        .collect::<Vec<_>>();
    if artworks_history.len() != history.len() {
        return Err(anyhow!("wrong or duplicate artwork id"));
    }
    let min_year = average_opt(artworks_history.iter().map(|a| a.date_year_min()));
    let max_year = average_opt(artworks_history.iter().map(|a| a.date_year_max()));
    let year_scoring = ArtworkScoring::year_scoring(&artworks, min_year, max_year);
    let mut types_of_objects = artworks_history
        .iter()
        .map(|a| a.type_of_object_id())
        .collect::<Vec<_>>();
    types_of_objects.sort_unstable();
    types_of_objects.dedup();
    let type_of_object_scoring =
        ArtworkScoring::type_of_object_scoring(&artworks, &types_of_objects);
    let mut emotions = artworks_history
        .iter()
        .flat_map(|a| emotions_str_to_vec(a.emotions()))
        .collect::<Vec<_>>();
    emotions.sort_unstable();
    emotions.dedup();
    let emotions_scoring = ArtworkScoring::emotions_scoring(&artworks, &emotions);
    let description_vector_sum = artworks_history
        .iter()
        .map(|a| a.description_vector())
        .fold(None, |mut acc: Option<Vec<u64>>, x| {
            if let Some(ref mut a) = acc {
                a.iter_mut().enumerate().for_each(|(i, v)| {
                    *v += x[i] as u64;
                });
                acc
            } else {
                Some(x.iter().map(|v| u64::from(*v)).collect::<Vec<_>>())
            }
        })
        .unwrap();
    let description_vector = description_vector_sum
        .iter()
        .map(|v| (*v / (history.len() as u64)) as u8)
        .collect::<Vec<_>>();
    let description_vector_scoring =
        ArtworkScoring::description_vector_scoring(&artworks, &description_vector);
    Ok(proposals_from_scorings(
        vec![
            year_scoring,
            type_of_object_scoring,
            emotions_scoring,
            description_vector_scoring,
        ],
        vec![
            "year_scoring",
            "type_of_object_scoring",
            "emotions_scoring",
            "description_vector_scoring",
        ],
        &artworks_history,
    )?
    .to_vec())
}

fn proposals_from_scorings(
    mut scorings: Vec<ArtworkScoring>,
    tags: Vec<&str>,
    taboo: &[&Artwork],
) -> Result<Vec<ResultArtwork>> {
    let emotions = Emotions::read_all().context("while retrieving emotions")?;
    let types_of_object =
        TypesOfObject::read_all().context("while retrieving types of object")?;
    let mut result = Vec::with_capacity(scorings.len());
    for i in 0..scorings.len() {
        scorings[i].invert();
        let mut owa = ArtworkScoring::owa_scoring(&scorings, OWA_WEIGHTS);
        owa.sort();
        if let Some((a, _)) = owa.iter().find(|(a, _)| {
            !result.iter().any(|r: &ResultArtwork| r.id() == a.id())
                && !taboo.iter().any(|r: &&Artwork| r.id() == a.id())
        }) {
            result.push(ResultArtwork::from_artwork(
                (*a).clone(),
                tags[i].to_string(),
                &emotions,
                &types_of_object,
            ));
        }
        scorings[i].invert();
    }
    Ok(result)
}

fn average_opt<T>(iter: impl Iterator<Item = Option<T>>) -> Option<T>
where
    T: Copy + From<u32> + Add<Output = T> + Div<Output = T> + Sum<T>,
{
    let (opt_s, c): (Option<T>, u32) = iter.fold((None, 0_u32), |(acc, n), x| {
        if let Some(v) = x {
            if let Some(a) = acc {
                (Some(v + a), n + 1)
            } else {
                (Some(v), 1)
            }
        } else {
            (acc, n)
        }
    });
    opt_s.map(|s| s / T::from(c))
}

#[derive(Clone)]
struct ArtworkScoring<'a>(Vec<(&'a Artwork, f64)>);

impl<'a> ArtworkScoring<'a> {
    fn year_scoring(artworks: &'a Artworks, min_year: Option<i64>, max_year: Option<i64>) -> Self {
        let gaps = artworks
            .iter()
            .map(|a| year_gap(min_year, max_year, a.date_year_min(), a.date_year_max()))
            .collect::<Vec<_>>();
        let max_gap = gaps.iter().max().copied().unwrap_or(0);
        Self(
            artworks
                .iter()
                .zip(gaps)
                .map(|(a, g)| (a, 1. - ((g as f64) / (max_gap as f64))))
                .collect(),
        )
    }

    fn type_of_object_scoring(artworks: &'a Artworks, types: &[i64]) -> Self {
        Self(
            artworks
                .iter()
                .map(|a| {
                    (
                        a,
                        types
                            .iter()
                            .map(|t| {
                                if *t == a.type_of_object_id() {
                                    1. / (types.len() as f64)
                                } else {
                                    0.
                                }
                            })
                            .sum(),
                    )
                })
                .collect(),
        )
    }

    fn emotions_scoring(artworks: &'a Artworks, emotions: &[String]) -> Self {
        Self(
            artworks
                .iter()
                .map(|a| (a, emotion_gap(emotions, &emotions_str_to_vec(a.emotions()))))
                .collect(),
        )
    }

    fn description_vector_scoring(artworks: &'a Artworks, description: &[u8]) -> Self {
        Self(
            artworks
                .iter()
                .map(|a| {
                    (
                        a,
                        a.description_vector()
                            .iter()
                            .zip(description)
                            .map(|(a, b)| u8::abs_diff(*a, *b) as f64)
                            .sum::<f64>()
                            / ((u8::MAX) as f64 * (description.len()) as f64),
                    )
                })
                .collect(),
        )
    }

    /// Creates a multicriteria scoring by aggregating other scorings using an ordered weighted averaging operator.
    /// Values for criteraia are sorted in descending ordered, weights are then applied in the same order they have been provided.
    fn owa_scoring(scorings: &[Self], weights: &[f64]) -> Self {
        assert_ne!(0, scorings.len());
        assert_eq!(scorings.len(), weights.len());
        let weights_sum = weights.iter().sum::<f64>();
        Self(
            scorings[0]
                .0
                .iter()
                .enumerate()
                .map(|(i, (a, _))| {
                    let mut values = scorings.iter().map(|s| s.0[i].1).collect::<Vec<_>>();
                    values.sort_by(|a, b| b.partial_cmp(a).unwrap());
                    let mc_value = values
                        .into_iter()
                        .zip(weights)
                        .map(|(v, w)| v * *w)
                        .sum::<f64>()
                        / weights_sum;
                    (*a, mc_value)
                })
                .collect(),
        )
    }

    fn iter(&self) -> impl Iterator<Item = &(&Artwork, f64)> {
        self.0.iter()
    }

    fn invert(&mut self) {
        self.0.iter_mut().for_each(|(_, s)| *s = 1. - *s);
    }

    fn sort(&mut self) {
        self.0.sort_by(|(_, a), (_, b)| b.partial_cmp(a).unwrap());
    }
}

fn year_gap(
    min_year0: Option<i64>,
    max_year0: Option<i64>,
    min_year1: Option<i64>,
    max_year1: Option<i64>,
) -> usize {
    if (min_year0.is_none() && max_year0.is_none()) || (min_year1.is_none() && max_year1.is_none())
    {
        return 0;
    }
    let min0 = min_year0.unwrap_or(max_year0.unwrap());
    let max0 = max_year0.unwrap_or(min_year0.unwrap());
    let min1 = min_year1.unwrap_or(max_year1.unwrap());
    let max1 = max_year1.unwrap_or(min_year1.unwrap());
    let overlap = |minx, maxx, y| y >= minx && y <= maxx;
    if overlap(min0, max0, min1)
        || overlap(min0, max0, max1)
        || overlap(min1, max1, min0)
        || overlap(min1, max1, max0)
    {
        return 0;
    }
    u64::min(i64::abs_diff(min0, max1), i64::abs_diff(min1, max0)) as usize
}

fn emotion_gap(emotions0: &[String], emotions1: &[String]) -> f64 {
    if emotions0.len() > emotions1.len() {
        return emotion_gap(emotions1, emotions0);
    }
    emotions0
        .iter()
        .map(|e| {
            if emotions1.contains(e) {
                1. / (emotions0.len() as f64)
            } else {
                0.
            }
        })
        .sum()
}

fn emotions_str_to_vec(emotions: &str) -> Vec<String> {
    emotions
        .split(',')
        .map(|s| s.trim().to_lowercase().to_string())
        .collect::<Vec<_>>()
}
